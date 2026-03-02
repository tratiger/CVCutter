"""Settings screen view-model."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Protocol

from cvcutter.domain.models.project import ProjectConfig


class SettingsWorkflow(Protocol):
    """Application service contract for settings commands."""

    def load_config(self) -> ProjectConfig:
        """Load persisted configuration."""
        ...

    def save_config(self, config: ProjectConfig) -> None:
        """Persist updated configuration."""
        ...

    def authenticate(self) -> bool:
        """Run authentication flow."""
        ...

    def test_connection(self) -> bool:
        """Test cloud/API connectivity."""
        ...

    def set_artifact_retention(self, policy: str) -> None:
        """Persist artifact retention policy."""
        ...

    def purge_artifacts(self, project_id: str) -> None:
        """Purge project artifacts."""
        ...


@dataclass
class SettingsViewModel:
    """State and commands for configuration and credential management."""

    workflow: SettingsWorkflow
    active_project_id: str = "active-project"
    config: ProjectConfig | None = None
    youtube_authenticated: bool = False
    gemini_configured: bool = False
    gpu_available: bool = False
    status_message: str = "設定を読み込みました。"
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Load initial configuration snapshot."""
        try:
            self.config = self.workflow.load_config()
            self.status_message = "設定を読み込みました。"
        except Exception:
            self.config = ProjectConfig()
            self.status_message = "設定の読み込みに失敗したため初期設定を使用します。"
        self.gemini_configured = bool(self.config.enable_gemini) if self.config is not None else False

    def update_config(self, key: str, value: Any) -> None:
        """Update one configuration field and persist immediately."""
        if self.config is None:
            self.config = ProjectConfig()
        if not hasattr(self.config, key):
            raise KeyError(f"未対応の設定キーです: {key}")
        previous = self.config
        try:
            updated = replace(self.config, **{key: value})
        except Exception as exc:
            self.errors.append(f"設定値が不正です: {exc}")
            self.status_message = "設定値が不正です。"
            return
        try:
            self.workflow.save_config(updated)
        except Exception as exc:
            self.config = previous
            self.errors.append(f"設定の保存に失敗しました: {exc}")
            self.status_message = "設定の保存に失敗しました。"
            return
        self.config = updated
        self.gemini_configured = bool(self.config.enable_gemini)
        self.status_message = "設定を更新しました。"

    def authenticate(self) -> bool:
        """Run authentication command and update state."""
        try:
            self.youtube_authenticated = self.workflow.authenticate()
        except Exception as exc:
            self.errors.append(f"認証に失敗しました: {exc}")
            self.youtube_authenticated = False
            self.status_message = "認証に失敗しました。"
            return False
        self.status_message = "認証に成功しました。" if self.youtube_authenticated else "認証に失敗しました。"
        return self.youtube_authenticated

    def test_connection(self) -> bool:
        """Run connectivity test command."""
        try:
            connected = self.workflow.test_connection()
        except Exception as exc:
            self.errors.append(f"接続テストに失敗しました: {exc}")
            self.status_message = "接続テストに失敗しました。"
            return False
        self.status_message = "接続テストに成功しました。" if connected else "接続テストに失敗しました。"
        return connected

    def set_artifact_retention(self, policy: str) -> None:
        """Update artifact retention policy."""
        try:
            self.workflow.set_artifact_retention(policy)
        except Exception as exc:
            self.errors.append(f"保持ポリシー更新に失敗しました: {exc}")
            self.status_message = "保持ポリシー更新に失敗しました。"
            return
        self.status_message = "成果物保持ポリシーを更新しました。"

    def purge_artifacts(self, project_id: str) -> None:
        """Purge project artifacts on demand."""
        try:
            self.workflow.purge_artifacts(project_id)
        except Exception as exc:
            self.errors.append(f"成果物削除に失敗しました: {exc}")
            self.status_message = "成果物削除に失敗しました。"
            return
        self.status_message = "成果物を削除しました。"

    def reset_to_defaults(self) -> None:
        """Reset settings to default configuration."""
        previous = self.config
        defaults = ProjectConfig()
        try:
            self.workflow.save_config(defaults)
        except Exception as exc:
            self.errors.append(f"初期化に失敗しました: {exc}")
            self.status_message = "設定の初期化に失敗しました。"
            self.config = previous
            return
        self.config = defaults
        self.gemini_configured = bool(self.config.enable_gemini)
        self.status_message = "設定を初期値に戻しました。"
