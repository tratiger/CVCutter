from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from cvcutter.domain.jobs.stages import JobState, WorkflowStage
from cvcutter.domain.policies.authorization_policy import enforce_executable_role


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class ProcessingJob:
    job_id: str
    role: str = "operator"
    classification_strategy: str = "content_based"
    low_confidence_threshold: int = 70
    input_video_path: str = ""
    input_audio_sources: list[str] = field(default_factory=list)
    metadata_source_refs: dict[str, object] = field(default_factory=dict)
    output_prefs: dict[str, object] = field(default_factory=dict)
    active_attempt: int = 1
    last_error_code: str | None = None
    created_at: datetime = field(default_factory=_utc_now)
    updated_at: datetime = field(default_factory=_utc_now)
    started_at: datetime | None = None
    ended_at: datetime | None = None
    stage_index: int = 0
    state: JobState = JobState.DRAFT
    completed_stages: list[WorkflowStage] = field(default_factory=list)
    _job_id_locked: bool = field(init=False, default=False, repr=False)

    def __post_init__(self) -> None:
        self._validate_job_id(self.job_id)
        self._validate_model_fields()
        object.__setattr__(self, "_job_id_locked", True)

    def __setattr__(self, name: str, value: object) -> None:
        if name == "job_id" and getattr(self, "_job_id_locked", False):
            raise AttributeError("job_id is immutable")
        object.__setattr__(self, name, value)

    @staticmethod
    def _validate_job_id(job_id: str) -> None:
        try:
            UUID(job_id)
        except ValueError as error:
            raise ValueError("job_id must be a valid UUID") from error

    def _validate_model_fields(self) -> None:
        if self.classification_strategy not in {"content_based", "timestamp_based"}:
            raise ValueError("classification_strategy must be content_based or timestamp_based")
        if self.low_confidence_threshold < 0 or self.low_confidence_threshold > 100:
            raise ValueError("low_confidence_threshold must be between 0 and 100")
        if self.active_attempt < 1:
            raise ValueError("active_attempt must be >= 1")
        if self.classification_strategy == "timestamp_based":
            required_refs = {"recording_time", "event_window_start", "event_window_end"}
            missing = required_refs - set(self.metadata_source_refs)
            if missing:
                raise ValueError(
                    "timestamp_based strategy requires recording_time/event_window_start/event_window_end"
                )

    def _touch(self) -> None:
        self.updated_at = _utc_now()

    @property
    def stages(self) -> list[WorkflowStage]:
        return list(WorkflowStage)

    def start(self) -> None:
        enforce_executable_role(self.role)
        if self.state == JobState.PAUSED:
            raise RuntimeError("cannot start job from state paused; mark job resumable first")
        if self.state not in {JobState.DRAFT, JobState.RESUMABLE, JobState.READY}:
            raise RuntimeError(f"cannot start job from state {self.state.value}")
        self.state = JobState.RUNNING
        if self.started_at is None:
            self.started_at = _utc_now()
        self.ended_at = None
        self._touch()

    def complete_current_stage(self) -> WorkflowStage:
        if self.state != JobState.RUNNING:
            raise RuntimeError("job must be running")
        if self.stage_index >= len(self.stages):
            raise RuntimeError("all stages already completed")
        stage = self.stages[self.stage_index]
        self.completed_stages.append(stage)
        self.stage_index += 1
        if self.stage_index >= len(self.stages):
            self.state = JobState.COMPLETED
            self.ended_at = _utc_now()
        self._touch()
        return stage

    def pause(self) -> None:
        if self.state == JobState.RUNNING:
            self.state = JobState.PAUSED
            self._touch()

    def mark_resumable(self) -> None:
        if self.state != JobState.PAUSED:
            raise RuntimeError("job can become resumable only from paused state")
        self.state = JobState.RESUMABLE
        self._touch()

    def fail(self) -> None:
        if self.state != JobState.RUNNING:
            raise RuntimeError(f"cannot fail job from state {self.state.value}")
        self.state = JobState.FAILED
        self.ended_at = _utc_now()
        self._touch()

    def cancel(self) -> None:
        if self.state != JobState.RUNNING:
            raise RuntimeError(f"cannot cancel job from state {self.state.value}")
        self.state = JobState.CANCELED
        self.ended_at = _utc_now()
        self._touch()
