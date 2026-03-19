from __future__ import annotations

from dataclasses import dataclass

from cvcutter.presentation.flet_app.viewmodel_helpers import localized
from cvcutter.presentation.flet_app.viewmodels.progress_dashboard_viewmodel import ProgressDashboardViewModel


@dataclass(slots=True)
class ProgressDashboardView:
    viewmodel: ProgressDashboardViewModel

    def summary(self) -> dict[str, object]:
        return {
            "title": localized("progress.title"),
            "current_stage": self.viewmodel.current_stage,
            "completed_stages": list(self.viewmodel.completed_stages),
            "pending_stages": list(self.viewmodel.pending_stages),
            "last_error_summary": self.viewmodel.last_error_summary,
            "timeline": list(self.viewmodel.timeline),
            "next_action": self.next_action_label(),
        }

    def next_action_label(self) -> str:
        if self.viewmodel.last_error_summary:
            return "修正後に再試行してください"
        if self.viewmodel.pending_stages:
            pending = list(self.viewmodel.pending_stages)
            if pending[0] == self.viewmodel.current_stage and len(pending) > 1:
                return f"次のステージ: {pending[1]}"
            return f"次のステージ: {pending[0]}"
        return "全ステージ完了"
