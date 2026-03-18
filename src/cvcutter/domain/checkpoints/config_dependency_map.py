from __future__ import annotations

from cvcutter.domain.jobs.stages import WorkflowStage, normalize_stage_value

_ALL_PROCESSING_STAGES = {stage.value for stage in WorkflowStage}
CONFIG_DEPENDENCY_MAP: dict[str, set[str]] = {
    "classification_strategy": {"classify", "segment_detect", "map_metadata", "export", "publish"},
    "low_confidence_threshold": {"segment_detect", "map_metadata", "export", "publish"},
    "metadata_source_refs": {"classify", "map_metadata", "publish"},
    "input_video_path": _ALL_PROCESSING_STAGES,
    "input_audio_sources": _ALL_PROCESSING_STAGES,
    "output_prefs": {"export", "publish"},
    "credentials": {"classify", "map_metadata", "publish"},
    "api_version_pin": {"classify", "map_metadata", "publish"},
    "segmentation.threshold": {"segment_detect"},
    "sync.reference": {"sync"},
    "publish.destination": {"publish"},
}

_STAGE_ORDER = [stage.value for stage in WorkflowStage]
_STAGE_INDEX = {stage: index for index, stage in enumerate(_STAGE_ORDER)}


def requires_resume_decision(changed_keys: set[str], current_stage: str) -> bool:
    affected_stages = set()
    for changed_key in changed_keys:
        affected_stages.update(_affected_by(changed_key))
    if not affected_stages:
        return False

    normalized_current_stage = normalize_stage_value(current_stage)
    current_index = _STAGE_INDEX.get(normalized_current_stage)
    if current_index is None:
        return True

    return any(_STAGE_INDEX[stage] <= current_index for stage in affected_stages if stage in _STAGE_INDEX)


def _affected_by(changed_key: str) -> set[str]:
    if changed_key in CONFIG_DEPENDENCY_MAP:
        return CONFIG_DEPENDENCY_MAP[changed_key]
    for key_group, stages in CONFIG_DEPENDENCY_MAP.items():
        if changed_key.startswith(f"{key_group}."):
            return stages
    return set()
