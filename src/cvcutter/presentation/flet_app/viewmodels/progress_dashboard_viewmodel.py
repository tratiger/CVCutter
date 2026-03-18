from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProgressDashboardViewModel:
    timeline: list[str] = field(default_factory=list)
    current_stage: str = "ingest"
    completed_stages: list[str] = field(default_factory=list)
    pending_stages: list[str] = field(default_factory=lambda: ["classify", "segment_detect", "sync", "map_metadata", "export", "publish"])
    last_error_summary: str = ""

    def add_event(self, event: str) -> None:
        self.timeline.append(event)

    def record_stage_update(self, stage: str, status: str, *, error_summary: str = "") -> None:
        self.current_stage = stage
        self.timeline.append(f"{stage}:{status}")
        if status == "completed" and stage not in self.completed_stages:
            self.completed_stages.append(stage)
        if stage in self.pending_stages and status == "completed":
            self.pending_stages.remove(stage)
        if error_summary:
            self.last_error_summary = error_summary
