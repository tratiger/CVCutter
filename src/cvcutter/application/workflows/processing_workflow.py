from __future__ import annotations

import json
import threading
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable
from uuid import NAMESPACE_URL, UUID, uuid5

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.services.classification_strategy_service import ClassificationStrategyService
from cvcutter.application.services.metadata_import_service import (
    CURRENT_SCHEMA_VERSION,
    validate_metadata_payload,
)
from cvcutter.application.services.metadata_mapping_service import map_segment_to_metadata
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.application.services.synchronization_service import choose_sync_path
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import JobState, WorkflowStage, normalize_stage_value
from cvcutter.domain.segmentation.threshold_policy import low_confidence_threshold
from cvcutter.infrastructure.integrations.adapters import ApprovedAdapters
from cvcutter.infrastructure.media.export_pipeline import export_media_file
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories
from cvcutter.shared.config import load_runtime_config


class WorkflowExecutionError(RuntimeError):
    def __init__(self, message: str, events: list[ProcessingEvent]) -> None:
        super().__init__(message)
        self.events = events


@dataclass(slots=True)
class ProcessingWorkflow:
    repositories: SqliteRepositories | None = None
    stage_handlers: dict[WorkflowStage, Callable[[ProcessingJob], None]] | None = None

    @staticmethod
    def _stop_lock_heartbeat(handle: tuple[threading.Event, threading.Thread] | None) -> None:
        if handle is None:
            return
        stop_event, thread = handle
        stop_event.set()
        thread.join(timeout=1.0)

    def _start_lock_heartbeat(
        self,
        job_id: str,
        heartbeat_failure: list[Exception],
    ) -> tuple[threading.Event, threading.Thread] | None:
        repositories = self.repositories
        if repositories is None:
            return None
        stop_event = threading.Event()

        def _heartbeat_loop() -> None:
            while not stop_event.wait(2.0):
                try:
                    repositories.touch_active_job_lock(job_id)
                except Exception as error:  # pragma: no cover - background failure path
                    heartbeat_failure.append(error)
                    stop_event.set()
                    break

        # Emit an immediate heartbeat so startup stale checks are based on current activity.
        repositories.touch_active_job_lock(job_id)
        thread = threading.Thread(target=_heartbeat_loop, name=f"job-lock-heartbeat-{job_id}", daemon=True)
        thread.start()
        return stop_event, thread

    @staticmethod
    def _parse_checkpoint_stage(stage_name: str) -> WorkflowStage | None:
        normalized = normalize_stage_value(stage_name)
        try:
            return WorkflowStage(normalized)
        except ValueError:
            return None

    def _persist_event(self, event: ProcessingEvent) -> None:
        if self.repositories is None:
            return
        payload = {
            "event_id": event.event_id,
            "event_schema_version": event.event_schema_version,
            "occurred_at": event.occurred_at,
            "stage_name": event.stage_name,
            "attempt": event.attempt,
            "severity": event.severity,
            "payload": event.payload,
        }
        self.repositories.append_event(
            event.event_type,
            event.job_id,
            json.dumps(payload, ensure_ascii=False),
            is_minimal_audit=self._is_minimal_audit_event(event.event_type),
        )

    def _record_checkpoint(self, job: ProcessingJob, stage: WorkflowStage, status: str) -> None:
        if self.repositories is None:
            return
        self.repositories.insert_checkpoint(
            job.job_id,
            stage.value,
            job.active_attempt,
            status,
            input_fingerprint=f"{job.job_id}:{stage.value}:{job.active_attempt}",
            output_fingerprint=None if status != "completed" else f"{job.job_id}:{stage.value}:completed",
        )

    @staticmethod
    def _is_minimal_audit_event(event_type: str) -> bool:
        if event_type in {"job.created", "job.state_changed", "stage.started", "stage.completed", "stage.failed"}:
            return True
        if event_type.startswith("retry.") or event_type == "publish.dedup_blocked":
            return True
        return False

    def _sync_job_state(self, job: ProcessingJob) -> None:
        if self.repositories is None:
            return
        self.repositories.upsert_job(job.job_id, job.state.value, job.role)

    @staticmethod
    def _normalize_identifier(value: str, *, prefix: str) -> str:
        try:
            UUID(value)
            return value
        except ValueError:
            return str(uuid5(NAMESPACE_URL, f"{prefix}:{value}"))

    @staticmethod
    def _segment_identifier(job_id: str, index: int) -> str:
        return str(uuid5(NAMESPACE_URL, f"{job_id}:segment:{index}"))

    @staticmethod
    def _mapping_identifier(job_id: str, segment_id: str) -> str:
        return str(uuid5(NAMESPACE_URL, f"{job_id}:mapping:{segment_id}"))

    @staticmethod
    def _audio_profile_identifier(job_id: str, source_name: str, source_kind: str, occurrence: int) -> str:
        return str(uuid5(NAMESPACE_URL, f"{job_id}:audio-profile:{source_kind}:{source_name}:{occurrence}"))

    @staticmethod
    def _event_payload_source(job: ProcessingJob) -> dict[str, object] | None:
        source = job.metadata_source_refs
        if not source:
            return None
        payload = dict(source)
        if "records" not in payload:
            return None
        payload.setdefault("schema_version", CURRENT_SCHEMA_VERSION)
        return payload

    @staticmethod
    def _adapter_state_path(job: ProcessingJob) -> Path:
        output_path_value = str(job.output_prefs.get("output_path", "")).strip()
        if output_path_value:
            candidate = Path(output_path_value)
            if candidate.suffix:
                return candidate.parent / f"{job.job_id}-adapter-idempotency.json"
            return candidate / f"{job.job_id}-adapter-idempotency.json"
        return Path.cwd() / f"{job.job_id}-adapter-idempotency.json"

    def _append_runtime_event(
        self,
        event_type: str,
        job: ProcessingJob,
        payload: dict[str, object],
        *,
        severity: str = "info",
    ) -> None:
        event = ProcessingEvent.new(
            event_type,
            job.job_id,
            payload,
            severity=severity,
            attempt=job.active_attempt,
        )
        self._persist_event(event)

    @staticmethod
    def _runtime_config_source(job: ProcessingJob) -> dict[str, str | int | bool]:
        destination_raw = job.output_prefs.get("destination", "youtube")
        title_overlay_raw = job.output_prefs.get("title_overlay_enabled", False)
        title_duration_raw = job.output_prefs.get("title_duration_seconds", 0)
        title_duration_value: str | int | bool
        if isinstance(title_duration_raw, (str, int)):
            title_duration_value = title_duration_raw
        else:
            title_duration_value = 0
        title_overlay_value: str | int | bool
        if isinstance(title_overlay_raw, (str, int, bool)):
            title_overlay_value = title_overlay_raw
        else:
            title_overlay_value = False
        return {
            "classification_strategy": job.classification_strategy,
            "low_confidence_threshold": job.low_confidence_threshold,
            "publish_destination": str(destination_raw),
            "title_overlay_enabled": title_overlay_value,
            "title_duration_seconds": title_duration_value,
        }

    def _run_ingest_stage(self, job: ProcessingJob) -> None:
        if not job.input_video_path:
            return
        input_video = Path(job.input_video_path)
        if not input_video.exists():
            raise FileNotFoundError(str(input_video))
        for audio_source in job.input_audio_sources:
            source_path = Path(audio_source)
            if not source_path.exists():
                raise FileNotFoundError(str(source_path))

    def _run_classify_stage(self, job: ProcessingJob) -> None:
        if self.repositories is None:
            return
        ClassificationStrategyService(self.repositories).set_strategy(job.job_id, job.classification_strategy)
        payload_source = self._event_payload_source(job)
        if payload_source is None:
            return
        source_format = str(payload_source.get("source_format", "json"))
        validation = validate_metadata_payload(payload_source, source_format=source_format)
        if not validation.ok:
            reasons = ",".join(validation.errors)
            raise ValueError(f"metadata_validation_failed:{reasons}")
        adapters = ApprovedAdapters(state_path=self._adapter_state_path(job))
        transcript = str(payload_source.get("transcript", "")).strip() or "classification-input-unavailable"
        result = adapters.classify_content(transcript, job_id=job.job_id)
        event_type = "classification.completed" if result.ok else "classification.failed"
        self._append_runtime_event(event_type, job, result.payload, severity="error" if not result.ok else "info")
        if not result.ok:
            raise RuntimeError(f"classification_failed:{result.error_code or result.category}")

    def _run_segment_detect_stage(self, job: ProcessingJob) -> None:
        if self.repositories is None or not job.input_video_path:
            return
        if self.repositories.list_segments(job.job_id):
            return
        threshold = low_confidence_threshold(job.low_confidence_threshold)
        confidence = min(100, max(threshold, 85))
        segment_id = self._segment_identifier(job.job_id, 1)
        self.repositories.insert_segment(segment_id, job.job_id, 0, 30_000, confidence, "pending")
        self._append_runtime_event(
            "segment.detected",
            job,
            {
                "segment_id": segment_id,
                "confidence_score": confidence,
            },
        )

    def _run_sync_stage(self, job: ProcessingJob) -> None:
        if self.repositories is None or not job.input_video_path:
            return
        embedded_audio_raw = job.output_prefs.get("has_embedded_video_audio", True)
        if isinstance(embedded_audio_raw, bool):
            has_embedded_video_audio = embedded_audio_raw
        elif isinstance(embedded_audio_raw, int):
            has_embedded_video_audio = embedded_audio_raw != 0
        elif isinstance(embedded_audio_raw, str):
            has_embedded_video_audio = embedded_audio_raw.strip().lower() in {"1", "true", "yes", "on"}
        else:
            has_embedded_video_audio = True
        sources: list[tuple[str, str]] = []
        if has_embedded_video_audio:
            sources.append(("embedded-video-audio", "embedded_video"))
        for index, audio_source in enumerate(job.input_audio_sources, start=1):
            source_name = Path(audio_source).name or f"external-audio-{index}"
            sources.append((source_name, "external"))
        if not sources:
            raise RuntimeError("no_audio_sources_available")
        sync_path = choose_sync_path(len(sources), has_embedded_video_audio)
        existing_profiles = self.repositories.list_audio_source_profiles(job.job_id)
        source_occurrence_counts: Counter[tuple[str, str]] = Counter()
        expected_profiles: list[tuple[str, str, str]] = []
        for source_name, source_kind in sources:
            source_key = (source_name, source_kind)
            source_occurrence_counts[source_key] += 1
            expected_profiles.append(
                (
                    self._audio_profile_identifier(
                        job.job_id,
                        source_name,
                        source_kind,
                        source_occurrence_counts[source_key],
                    ),
                    source_name,
                    source_kind,
                )
            )
        existing_sources_by_profile_id = {item[0]: (item[1], item[2]) for item in existing_profiles}
        remaining_existing_source_counts = Counter((item[1], item[2]) for item in existing_profiles)
        matched_expected_profile_ids: set[str] = set()

        for profile_id, source_name, source_kind in expected_profiles:
            existing_source = existing_sources_by_profile_id.get(profile_id)
            if existing_source != (source_name, source_kind):
                continue
            matched_expected_profile_ids.add(profile_id)
            source_key = (source_name, source_kind)
            if remaining_existing_source_counts[source_key] > 0:
                remaining_existing_source_counts[source_key] -= 1

        for profile_id, source_name, source_kind in expected_profiles:
            if profile_id in matched_expected_profile_ids:
                continue
            source_key = (source_name, source_kind)
            if remaining_existing_source_counts[source_key] > 0:
                remaining_existing_source_counts[source_key] -= 1
                continue
            self.repositories.insert_audio_source_profile(
                profile_id,
                job.job_id,
                source_name,
                source_kind,
                0,
                0.0,
                0.0,
                "simple",
                "ok",
                "not_required",
            )
        self._append_runtime_event(
            "sync.path_selected",
            job,
            {
                "sync_path": sync_path,
                "source_count": len(sources),
            },
        )

    def _run_map_metadata_stage(self, job: ProcessingJob) -> None:
        if self.repositories is None:
            return
        payload_source = self._event_payload_source(job)
        if payload_source is None:
            return
        source_format = str(payload_source.get("source_format", "json"))
        validation = validate_metadata_payload(payload_source, source_format=source_format)
        if not validation.ok:
            reasons = ",".join(validation.errors)
            raise ValueError(f"metadata_validation_failed:{reasons}")
        if not validation.records:
            raise ValueError("metadata_validation_failed:no_records")
        segments = self.repositories.list_segments(job.job_id)
        if not segments:
            self._run_segment_detect_stage(job)
            segments = self.repositories.list_segments(job.job_id)
        if not segments:
            return
        existing_mappings = self.repositories.list_metadata_mappings(job.job_id)
        mapped_segment_ids = {mapping[1] for mapping in existing_mappings}
        if all(segment[0] in mapped_segment_ids for segment in segments):
            return
        for index, segment in enumerate(segments):
            segment_id = segment[0]
            if segment_id in mapped_segment_ids:
                continue
            record_index = min(index, len(validation.records) - 1)
            record = validation.records[record_index]
            ok, reason = map_segment_to_metadata(segment_id, record)
            if not ok:
                raise ValueError(f"metadata_mapping_failed:{reason}")
            raw_tags = record.get("tags", [])
            tags = [str(tag) for tag in raw_tags] if isinstance(raw_tags, list) else []
            mapping_id = self._mapping_identifier(job.job_id, segment_id)
            self.repositories.insert_metadata_mapping(
                mapping_id,
                job.job_id,
                segment_id,
                str(payload_source.get("schema_version", CURRENT_SCHEMA_VERSION)),
                str(record["segment_title"]),
                str(record.get("description", "")),
                tags,
                {"record_index": record_index, "mapping_strategy": "catalog_order"},
                str(record["publish_visibility"]),
                "valid",
            )
        self._append_runtime_event(
            "metadata.mapped",
            job,
            {"mapping_count": len(segments)},
        )

    def _run_export_stage(self, job: ProcessingJob) -> None:
        if not job.input_video_path:
            return
        output_path_value = str(job.output_prefs.get("output_path", "")).strip()
        input_path = Path(job.input_video_path)
        runtime_config = load_runtime_config(self._runtime_config_source(job))
        output_format = str(job.output_prefs.get("output_format", "mp4"))
        if output_path_value:
            requested_output = Path(output_path_value)
            if requested_output.suffix:
                output_path = requested_output
            else:
                output_path = requested_output / f"{input_path.stem}.export.{output_format}"
        else:
            output_path = input_path.with_name(f"{input_path.stem}.export.{output_format}")
        exported = export_media_file(
            input_path,
            output_path,
            output_format=output_format,
            title_overlay_enabled=runtime_config.title_overlay_enabled,
            title_duration_seconds=runtime_config.title_duration_seconds,
        )
        job.output_prefs["output_path"] = str(exported)
        self._append_runtime_event(
            "export.completed",
            job,
            {
                "output_path": str(exported),
                "output_format": output_format,
            },
        )

    def _run_publish_stage(self, job: ProcessingJob) -> None:
        if self.repositories is None:
            return
        segments = self.repositories.list_segments(job.job_id)
        if not segments:
            return
        runtime_config = load_runtime_config(self._runtime_config_source(job))
        adapters = ApprovedAdapters(state_path=self._adapter_state_path(job))
        for segment in segments:
            segment_id = segment[0]
            normalized_segment_id = self._normalize_identifier(
                segment_id,
                prefix=f"{job.job_id}:publish-segment",
            )
            result = adapters.publish_segment(
                normalized_segment_id,
                {"destination": runtime_config.publish_destination},
                job_id=job.job_id,
            )
            if result.category == "success":
                event_type = (
                    "publish.dedup_blocked"
                    if result.idempotency_outcome == "duplicate_suppressed"
                    else "publish.completed"
                )
                self._append_runtime_event(event_type, job, result.payload)
                continue
            self._append_runtime_event("publish.failed", job, result.payload, severity="error")
            raise RuntimeError(f"publish_failed:{result.error_code or result.category}")

    def _default_stage_handler(self, stage: WorkflowStage) -> Callable[[ProcessingJob], None] | None:
        handlers: dict[WorkflowStage, Callable[[ProcessingJob], None]] = {
            WorkflowStage.INGEST: self._run_ingest_stage,
            WorkflowStage.CLASSIFY: self._run_classify_stage,
            WorkflowStage.SEGMENT_DETECT: self._run_segment_detect_stage,
            WorkflowStage.SYNC: self._run_sync_stage,
            WorkflowStage.MAP_METADATA: self._run_map_metadata_stage,
            WorkflowStage.EXPORT: self._run_export_stage,
            WorkflowStage.PUBLISH: self._run_publish_stage,
        }
        return handlers.get(stage)

    def _resolve_stage_handler(self, stage: WorkflowStage) -> Callable[[ProcessingJob], None] | None:
        if self.stage_handlers is not None:
            configured = self.stage_handlers.get(stage)
            if configured is not None:
                return configured
        return self._default_stage_handler(stage)

    def _append_event(self, event_log: list[ProcessingEvent], event: ProcessingEvent) -> None:
        event_log.append(event)
        self._persist_event(event)

    def _resolve_resume_stage(self, job: ProcessingJob) -> WorkflowStage | None:
        if self.repositories is not None:
            checkpoints = self.repositories.list_checkpoints(job.job_id)
            completed_from_db: list[WorkflowStage] = []
            for stage_name, attempt, status in checkpoints:
                if attempt != job.active_attempt or status != "completed":
                    continue
                stage = self._parse_checkpoint_stage(stage_name)
                if stage is None:
                    raise RuntimeError(f"unsupported_checkpoint_stage:{stage_name}")
                completed_from_db.append(stage)
            if completed_from_db:
                ordered: list[WorkflowStage] = []
                for stage in WorkflowStage:
                    if stage in completed_from_db:
                        ordered.append(stage)
                if ordered:
                    return select_first_incomplete_stage(ordered)
        return select_first_incomplete_stage(job.completed_stages)

    @staticmethod
    def _restore_completed_stages_from_checkpoints(
        completed_stages: list[tuple[str, int, str]],
        *,
        attempt: int,
    ) -> list[WorkflowStage]:
        ordered: list[WorkflowStage] = []
        for stage in WorkflowStage:
            for stage_name, checkpoint_attempt, status in completed_stages:
                if checkpoint_attempt != attempt or status != "completed":
                    continue
                normalized = normalize_stage_value(stage_name)
                if normalized == stage.value and stage not in ordered:
                    ordered.append(stage)
                    break
        return ordered

    def _prepare_resume_job(self, job: ProcessingJob) -> WorkflowStage | None:
        if self.repositories is None:
            next_stage = select_first_incomplete_stage(job.completed_stages)
            if next_stage is None:
                return None
            if job.state == JobState.PAUSED:
                job.mark_resumable()
                job.start()
            elif job.state == JobState.RESUMABLE:
                job.start()
            elif job.state != JobState.RUNNING:
                job.start()
            return next_stage

        checkpoints = self.repositories.list_checkpoints(job.job_id)
        completed_stages = self._restore_completed_stages_from_checkpoints(
            checkpoints,
            attempt=job.active_attempt,
        )
        if completed_stages:
            job.completed_stages = list(completed_stages)
            job.stage_index = len(completed_stages)
        next_stage = select_first_incomplete_stage(job.completed_stages)
        if next_stage is None:
            return None
        if job.state == JobState.PAUSED:
            job.mark_resumable()
        if job.state in {JobState.DRAFT, JobState.READY, JobState.RESUMABLE}:
            job.start()
        elif job.state != JobState.RUNNING:
            raise RuntimeError(f"resume_not_allowed_from_state:{job.state.value}")
        self._sync_job_state(job)
        return next_stage

    @staticmethod
    def _rollback_stage_completion(job: ProcessingJob, stage: WorkflowStage) -> None:
        if job.completed_stages and job.completed_stages[-1] == stage:
            job.completed_stages.pop()
        if job.stage_index > 0:
            job.stage_index -= 1
        job.state = JobState.RUNNING
        job.ended_at = None

    @staticmethod
    def _mark_job_completed(job: ProcessingJob) -> None:
        now = datetime.now(timezone.utc)
        job.state = JobState.COMPLETED
        if job.ended_at is None:
            job.ended_at = now
        job.updated_at = now

    def _run_from_prepared_state(self, job: ProcessingJob) -> list[ProcessingEvent]:
        event_log: list[ProcessingEvent] = []
        self._sync_job_state(job)
        heartbeat_failure: list[Exception] = []
        heartbeat_handle: tuple[threading.Event, threading.Thread] | None = None
        try:
            heartbeat_handle = self._start_lock_heartbeat(job.job_id, heartbeat_failure)
            self._append_event(
                event_log,
                ProcessingEvent.new(
                    "job.created",
                    job.job_id,
                    {"state": job.state.value},
                    severity="info",
                    attempt=job.active_attempt,
                ),
            )
            while job.state.value == "running":
                if heartbeat_failure:
                    raise RuntimeError(str(heartbeat_failure[0]))
                stage_name = "unknown"
                current_stage: WorkflowStage | None = None
                try:
                    stage = job.stages[job.stage_index]
                    current_stage = stage
                    stage_name = stage.value
                    self._append_event(
                        event_log,
                        ProcessingEvent.new(
                            "stage.started",
                            job.job_id,
                            {"state": job.state.value},
                            stage_name=stage_name,
                            attempt=job.active_attempt,
                        ),
                    )
                    handler = self._resolve_stage_handler(stage)
                    if handler is not None:
                        handler(job)
                    completed_stage = job.complete_current_stage()
                    try:
                        self._record_checkpoint(job, completed_stage, "completed")
                    except Exception:
                        self._rollback_stage_completion(job, completed_stage)
                        raise
                    self._sync_job_state(job)
                except Exception as error:
                    failure_error = error
                    if job.state.value == "running":
                        try:
                            job.fail()
                            self._sync_job_state(job)
                        except Exception as transition_error:  # pragma: no cover - defensive guard
                            failure_error = transition_error
                    if current_stage is not None and current_stage not in job.completed_stages:
                        try:
                            self._record_checkpoint(job, current_stage, "failed")
                        except Exception:
                            pass
                    try:
                        self._append_event(
                            event_log,
                            ProcessingEvent.new(
                                "stage.failed",
                                job.job_id,
                                {"state": job.state.value},
                                severity="error",
                                stage_name=stage_name,
                                attempt=job.active_attempt,
                            ),
                        )
                        self._append_event(
                            event_log,
                            ProcessingEvent.new(
                                "job.state_changed",
                                job.job_id,
                                {"stage": stage_name, "state": job.state.value},
                                severity="error",
                                attempt=job.active_attempt,
                            ),
                        )
                    except Exception:
                        pass
                    raise WorkflowExecutionError(str(failure_error), list(event_log)) from error
                self._append_event(
                    event_log,
                    ProcessingEvent.new(
                        "stage.completed",
                        job.job_id,
                        {"state": job.state.value},
                        stage_name=completed_stage.value,
                        attempt=job.active_attempt,
                    ),
                )
                self._append_event(
                    event_log,
                    ProcessingEvent.new(
                        "job.state_changed",
                        job.job_id,
                        {"stage": completed_stage.value, "state": job.state.value},
                        attempt=job.active_attempt,
                    ),
                )
        except Exception as startup_error:
            if isinstance(startup_error, WorkflowExecutionError):
                raise
            failure_error = startup_error
            if job.state.value == "running":
                try:
                    job.fail()
                    self._sync_job_state(job)
                except Exception as transition_error:  # pragma: no cover - defensive guard
                    failure_error = transition_error
            raise WorkflowExecutionError(str(failure_error), list(event_log)) from startup_error
        finally:
            self._stop_lock_heartbeat(heartbeat_handle)
        return event_log

    def run_until_complete(self, job: ProcessingJob) -> list[ProcessingEvent]:
        job.start()
        return self._run_from_prepared_state(job)

    def resume(self, job: ProcessingJob) -> str:
        next_stage = self._resolve_resume_stage(job)
        if next_stage is None:
            self._mark_job_completed(job)
            self._sync_job_state(job)
            return "done"
        prepared_stage = self._prepare_resume_job(job)
        if prepared_stage is None:
            self._mark_job_completed(job)
            self._sync_job_state(job)
            return "done"
        events = self._run_from_prepared_state(job)
        if not events:
            raise WorkflowExecutionError("resume_execution_produced_no_events", [])
        return prepared_stage.value
