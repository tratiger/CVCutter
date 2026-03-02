"""JSON-backed adapter for global quota-state persistence."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from cvcutter.domain.models.upload import QuotaState
from cvcutter.domain.services.quota_state_store import QuotaStateStore
from cvcutter.shared.time_utils import pt_midnight_utc


class JsonQuotaStateStore(QuotaStateStore):
    """Persist and load global YouTube quota state as JSON."""

    def __init__(self, base_dir: Path) -> None:
        """Initialize the store with the per-user app data base directory."""
        self._base_dir = Path(base_dir)
        self._file_path = self._base_dir / "quota_state.json"

    def load(self) -> QuotaState | None:
        """Load global quota state, returning None when unavailable or invalid."""
        payload = self._read_json(self._file_path)
        if not isinstance(payload, dict):
            return None
        return self._quota_state_from_raw(payload)

    def save(self, state: QuotaState) -> None:
        """Persist global quota state."""
        self._write_json(self._file_path, asdict(state))

    def load_or_default(self, daily_limit: int = 10_000) -> QuotaState:
        """Load persisted quota state or provide a safe default snapshot."""
        loaded = self.load()
        if loaded is not None:
            return loaded
        now = datetime.now(UTC)
        return QuotaState(
            daily_limit=daily_limit,
            daily_used=0,
            reset_timestamp_utc=pt_midnight_utc(),
            last_updated=now,
        )

    def reset_if_due(self, now_utc: datetime | None = None) -> QuotaState:
        """Reset persisted quota state when reset timestamp has passed."""
        state = self.load_or_default()
        current = now_utc or datetime.now(UTC)
        if current < state.reset_timestamp_utc:
            return state
        reset_state = state.reset()
        self.save(reset_state)
        return reset_state

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        """Parse datetime values from persisted JSON payload."""
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    def _quota_state_from_raw(self, raw: dict[str, Any]) -> QuotaState | None:
        """Build QuotaState from raw JSON payload."""
        reset_timestamp_utc = self._parse_datetime(raw.get("reset_timestamp_utc"))
        last_updated = self._parse_datetime(raw.get("last_updated"))
        if reset_timestamp_utc is None or last_updated is None:
            return None

        try:
            return QuotaState(
                daily_limit=int(raw.get("daily_limit", 10_000)),
                daily_used=int(raw.get("daily_used", 0)),
                reset_timestamp_utc=reset_timestamp_utc,
                last_updated=last_updated,
            )
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _write_json(path: Path, data: Any) -> None:
        """Safely write JSON data to disk."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(data, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        except (OSError, TypeError, ValueError):
            return

    @staticmethod
    def _read_json(path: Path) -> Any | None:
        """Safely read JSON data from disk."""
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
