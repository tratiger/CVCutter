"""JSON-backed adapter for global project configuration persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from cvcutter.domain.models.project import ProjectConfig


class JsonConfig:
    """Read and write global configuration in `config.json`."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the adapter with the per-user app data base directory."""
        self._base_dir = Path(base_dir)
        self._file_path = self._base_dir / "config.json"

    def load_config(self) -> ProjectConfig:
        """Load typed project configuration with safe fallback to defaults."""
        raw = self.load_raw()
        if not raw:
            return ProjectConfig()
        try:
            return ProjectConfig(**raw)
        except (TypeError, ValueError):
            return ProjectConfig()

    def save_config(self, config: ProjectConfig) -> None:
        """Persist typed project configuration."""
        self.save_raw(asdict(config))

    def load_raw(self) -> dict[str, Any]:
        """Load raw configuration mapping from JSON."""
        try:
            payload = json.loads(self._file_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return {}
        return payload if isinstance(payload, dict) else {}

    def save_raw(self, data: dict[str, Any]) -> None:
        """Persist raw configuration mapping as JSON."""
        try:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            self._file_path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError):
            return
