from __future__ import annotations

from cvcutter.domain.jobs.stages import WorkflowStage

CONFIG_DEPENDENCY_MAP: dict[str, set[str]] = {
    "segmentation.threshold": {"segment"},
    "sync.reference": {"sync"},
    "publish.destination": {"publish"},
}

_STAGE_ORDER = [stage.value for stage in WorkflowStage]
_STAGE_INDEX = {stage: index for index, stage in enumerate(_STAGE_ORDER)}


def requires_resume_decision(changed_keys: set[str], current_stage: str) -> bool:
    affected = {stage for key in changed_keys for stage in CONFIG_DEPENDENCY_MAP.get(key, set())}
    if not affected:
        return False
    current_index = _STAGE_INDEX.get(current_stage)
    if current_index is None:
        return True
    return any(_STAGE_INDEX.get(stage, 0) <= current_index for stage in affected)
