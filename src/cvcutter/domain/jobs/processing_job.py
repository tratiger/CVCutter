from __future__ import annotations

from dataclasses import dataclass, field

from cvcutter.domain.jobs.stages import JobState, WorkflowStage
from cvcutter.domain.policies.authorization_policy import enforce_executable_role


@dataclass(slots=True)
class ProcessingJob:
    job_id: str
    role: str = "operator"
    stage_index: int = 0
    state: JobState = JobState.DRAFT
    completed_stages: list[WorkflowStage] = field(default_factory=list)

    @property
    def stages(self) -> list[WorkflowStage]:
        return list(WorkflowStage)

    def start(self) -> None:
        enforce_executable_role(self.role)
        if self.state not in {JobState.DRAFT, JobState.PAUSED, JobState.RESUMABLE, JobState.READY}:
            raise RuntimeError(f"cannot start job from state {self.state.value}")
        self.state = JobState.RUNNING

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
        return stage

    def pause(self) -> None:
        if self.state == JobState.RUNNING:
            self.state = JobState.PAUSED

    def mark_resumable(self) -> None:
        if self.state != JobState.PAUSED:
            raise RuntimeError("job can become resumable only from paused state")
        self.state = JobState.RESUMABLE

    def fail(self) -> None:
        if self.state != JobState.RUNNING:
            raise RuntimeError(f"cannot fail job from state {self.state.value}")
        self.state = JobState.FAILED

    def cancel(self) -> None:
        if self.state != JobState.RUNNING:
            raise RuntimeError(f"cannot cancel job from state {self.state.value}")
        self.state = JobState.CANCELED
