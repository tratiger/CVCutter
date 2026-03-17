from __future__ import annotations

from cvcutter.domain.jobs.stages import WorkflowStage


def select_first_incomplete_stage(completed: list[WorkflowStage]) -> WorkflowStage | None:
    for stage in WorkflowStage:
        if stage not in completed:
            return stage
    return None
