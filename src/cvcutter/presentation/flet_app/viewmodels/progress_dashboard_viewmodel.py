from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class ProgressDashboardViewModel:
    timeline: list[str] = field(default_factory=list)

    def add_event(self, event: str) -> None:
        self.timeline.append(event)
