from __future__ import annotations

import json
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from tempfile import gettempdir
from uuid import uuid4

from cvcutter.domain.policies.destination_policy import ensure_destination_allowed

_RESULT_CATEGORY = {"success", "transient", "blocking", "policy"}
_NEXT_ACTION = {"none", "retry_later", "check_credentials", "fix_policy_configuration"}


@dataclass(slots=True)
class AdapterResult:
    provider: str
    operation: str
    category: str
    terminal: bool
    idempotency_outcome: str
    recommended_next_action: str
    message: str
    error_code: str | None = None
    retry_after_seconds: int | None = None
    correlation_id: str | None = None
    external_object_id: str | None = None

    def __post_init__(self) -> None:
        if self.category not in _RESULT_CATEGORY:
            raise ValueError(f"invalid_result_category:{self.category}")
        if self.recommended_next_action not in _NEXT_ACTION:
            raise ValueError(f"invalid_next_action:{self.recommended_next_action}")

    @property
    def ok(self) -> bool:
        return self.category == "success"

    @property
    def payload(self) -> dict[str, object]:
        return {
            "provider": self.provider,
            "operation": self.operation,
            "category": self.category,
            "error_code": self.error_code,
            "retry_after_seconds": self.retry_after_seconds,
            "terminal": self.terminal,
            "correlation_id": self.correlation_id,
            "idempotency_outcome": self.idempotency_outcome,
            "external_object_id": self.external_object_id,
            "message": self.message,
            "recommended_next_action": self.recommended_next_action,
        }


class ApprovedAdapters:
    def __init__(self, *, state_path: Path | None = None) -> None:
        self._state_path = state_path or Path(gettempdir()) / "cvcutter_adapter_idempotency.json"
        self._seen_publish_keys: set[tuple[str, str, str]] = set()

    def publish_segment(
        self,
        segment_id: str,
        metadata: dict[str, object],
        *,
        job_id: str,
    ) -> AdapterResult:
        mandatory = {"destination"}
        if not mandatory.issubset(metadata):
            return AdapterResult(
                provider="youtube",
                operation="publish_segment",
                category="blocking",
                terminal=True,
                idempotency_outcome="unknown",
                recommended_next_action="fix_policy_configuration",
                message="missing required publish metadata fields",
                error_code="missing_publish_fields",
            )

        destination = str(metadata["destination"])
        try:
            ensure_destination_allowed("youtube", destination)
        except ValueError:
            return AdapterResult(
                provider="youtube",
                operation="publish_segment",
                category="policy",
                terminal=True,
                idempotency_outcome="unknown",
                recommended_next_action="fix_policy_configuration",
                message="destination is not approved by policy",
                error_code="destination_not_allowed",
            )

        if bool(metadata.get("simulate_http_429")):
            return AdapterResult(
                provider="youtube",
                operation="publish_segment",
                category="transient",
                terminal=False,
                idempotency_outcome="unknown",
                recommended_next_action="retry_later",
                message="provider requested retry after throttling",
                error_code="HTTP_429",
                retry_after_seconds=17,
                correlation_id=str(uuid4()),
            )

        dedup_key = (job_id, segment_id, destination)
        try:
            with self._state_lock():
                loaded_keys, load_error = self._safe_load_seen_publish_keys()
                if load_error is not None:
                    error_code = "idempotency_store_corrupt"
                    if load_error == "state_read_error":
                        error_code = "idempotency_store_unreadable"
                    return AdapterResult(
                        provider="youtube",
                        operation="publish_segment",
                        category="blocking",
                        terminal=True,
                        idempotency_outcome="unknown",
                        recommended_next_action="fix_policy_configuration",
                        message="idempotency store is corrupted; repair local runtime state",
                        error_code=error_code,
                    )
                self._seen_publish_keys = loaded_keys
                if dedup_key in self._seen_publish_keys:
                    return AdapterResult(
                        provider="youtube",
                        operation="publish_segment",
                        category="success",
                        terminal=True,
                        idempotency_outcome="duplicate_suppressed",
                        recommended_next_action="none",
                        message="duplicate publish suppressed by idempotency key",
                        correlation_id=str(uuid4()),
                    )

                self._seen_publish_keys.add(dedup_key)
                try:
                    self._persist_seen_publish_keys()
                except OSError:
                    return AdapterResult(
                        provider="youtube",
                        operation="publish_segment",
                        category="blocking",
                        terminal=True,
                        idempotency_outcome="unknown",
                        recommended_next_action="fix_policy_configuration",
                        message="failed to persist idempotency state",
                        error_code="idempotency_store_write_failed",
                    )
        except OSError:
            return AdapterResult(
                provider="youtube",
                operation="publish_segment",
                category="blocking",
                terminal=True,
                idempotency_outcome="unknown",
                recommended_next_action="fix_policy_configuration",
                message="failed to acquire idempotency store lock",
                error_code="idempotency_store_lock_failed",
            )
        return AdapterResult(
            provider="youtube",
            operation="publish_segment",
            category="success",
            terminal=True,
            idempotency_outcome="performed",
            recommended_next_action="none",
            message="publish completed successfully",
            correlation_id=str(uuid4()),
            external_object_id=f"yt:{segment_id}",
        )

    def fetch_form_responses(self, form_id: str, *, job_id: str) -> AdapterResult:
        return AdapterResult(
            provider="google_forms",
            operation="fetch_form_responses",
            category="success",
            terminal=True,
            idempotency_outcome="performed",
            recommended_next_action="none",
            message="metadata fetched",
            correlation_id=f"{job_id}:{form_id}",
        )

    def classify_content(self, text: str, *, job_id: str) -> AdapterResult:
        return AdapterResult(
            provider="configured_ai",
            operation="classify_content",
            category="success",
            terminal=True,
            idempotency_outcome="performed",
            recommended_next_action="none",
            message="classification completed",
            correlation_id=f"{job_id}:classification",
            external_object_id=text[:32],
        )

    def _safe_load_seen_publish_keys(
        self,
    ) -> tuple[set[tuple[str, str, str]], str | None]:
        try:
            return self._load_seen_publish_keys(), None
        except json.JSONDecodeError:
            return set(), "json_decode_error"
        except ValueError:
            return set(), "invalid_state_shape"
        except OSError:
            return set(), "state_read_error"

    def _load_seen_publish_keys(self) -> set[tuple[str, str, str]]:
        if not self._state_path.exists():
            return set()
        payload = json.loads(self._state_path.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("adapter idempotency store is malformed")
        keys: set[tuple[str, str, str]] = set()
        for item in payload:
            if (
                isinstance(item, list)
                and len(item) == 3
                and all(isinstance(part, str) for part in item)
            ):
                keys.add((item[0], item[1], item[2]))
                continue
            raise ValueError("adapter idempotency key entry is malformed")
        return keys

    def _persist_seen_publish_keys(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = [list(item) for item in sorted(self._seen_publish_keys)]
        temp_path = self._state_path.with_suffix(f"{self._state_path.suffix}.{uuid4().hex}.tmp")
        temp_path.write_text(json.dumps(serialized), encoding="utf-8")
        temp_path.replace(self._state_path)

    @contextmanager
    def _state_lock(self):
        lock_path = self._state_path.with_suffix(f"{self._state_path.suffix}.lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+b") as lock_file:
            if os.name == "nt":
                import msvcrt

                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                if os.name == "nt":
                    import msvcrt

                    lock_file.seek(0)
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
