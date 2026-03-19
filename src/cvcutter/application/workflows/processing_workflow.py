from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from typing import Callable

from cvcutter.application.dto.events import ProcessingEvent
from cvcutter.application.services.resume_service import select_first_incomplete_stage
from cvcutter.domain.jobs.processing_job import ProcessingJob
from cvcutter.domain.jobs.stages import JobState, WorkflowStage, normalize_stage_value
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


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
        self.repositories.append_event(event.event_type, event.job_id, json.dumps(payload, ensure_ascii=False))

    def _record_checkpoint(self, job: ProcessingJob, stage: WorkflowStage, status: str) -> None:
        if self.repositories is None:
            return
        self.repositories.insert_checkpoint(job.job_id, stage.value, job.active_attempt, status)

    def _sync_job_state(self, job: ProcessingJob) -> None:
        if self.repositories is None:
            return
        self.repositories.upsert_job(job.job_id, job.state.value, job.role)

    def _resolve_stage_handler(self, stage: WorkflowStage) -> Callable[[ProcessingJob], None] | None:
        if self.stage_handlers is None:
            return None
        return self.stage_handlers.get(stage)

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
    def _rollback_stage_completion(job: ProcessingJob, stage: WorkflowStage) -> None:
        if job.completed_stages and job.completed_stages[-1] == stage:
            job.completed_stages.pop()
        if job.stage_index > 0:
            job.stage_index -= 1
        job.state = JobState.RUNNING
        job.ended_at = None

    def run_until_complete(self, job: ProcessingJob) -> list[ProcessingEvent]:
        event_log: list[ProcessingEvent] = []
        job.start()
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

    def resume(self, job: ProcessingJob) -> str:
        next_stage = self._resolve_resume_stage(job)
        return "done" if next_stage is None else next_stage.value
