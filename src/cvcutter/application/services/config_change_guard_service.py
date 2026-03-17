from __future__ import annotations

from dataclasses import dataclass

from cvcutter.domain.checkpoints.config_dependency_map import requires_resume_decision


@dataclass(slots=True)
class ConfigChangeGuardService:
    def assess(self, changed_keys: set[str], stage: str) -> str:
        return "decision_required" if requires_resume_decision(changed_keys, stage) else "continue"
