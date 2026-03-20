from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from cvcutter.infrastructure.integrations.adapters import AdapterResult, ApprovedAdapters
from cvcutter.infrastructure.persistence.repositories import SqliteRepositories


@dataclass(slots=True)
class PublishResult:
    status: str
    event_type: str
    payload: dict[str, object]


class PublishAdapter(Protocol):
    def publish_segment(
        self,
        segment_id: str,
        metadata: dict[str, object],
        *,
        job_id: str,
    ) -> AdapterResult:
        ...


class PublishingService:
    def __init__(
        self,
        repositories: SqliteRepositories,
        job_id: str = "00000000-0000-0000-0000-000000000000",
        *,
        adapters: PublishAdapter | None = None,
    ) -> None:
        self.repositories = repositories
        self.job_id = job_id
        self.adapters = adapters or ApprovedAdapters(state_path=self._default_adapter_state_path())

    def _default_adapter_state_path(self) -> Path:
        return self.repositories.db_path.parent / f"{self.job_id}-service-adapter-idempotency.json"

    @staticmethod
    def _normalize_identifier(value: str, *, namespace: str) -> str:
        try:
            UUID(value)
            return value
        except ValueError:
            return str(uuid5(NAMESPACE_URL, f"{namespace}:{value}"))

    def publish(
        self,
        segment_id: str,
        destination: str = "youtube",
        *,
        metadata: dict[str, object] | None = None,
    ) -> PublishResult:
        normalized_segment_id = self._normalize_identifier(
            segment_id,
            namespace=f"{self.job_id}:publish-segment",
        )
        payload = dict(metadata or {})
        if "destination" not in payload:
            payload["destination"] = destination
        effective_destination = str(payload.get("destination", destination))
        try:
            self.repositories.store_publish_key(self.job_id, normalized_segment_id, effective_destination)
        except sqlite3.IntegrityError:
            return PublishResult(
                "blocked",
                "publish.dedup_blocked",
                {
                    "provider": "youtube",
                    "operation": "publish_segment",
                    "category": "success",
                    "idempotency_outcome": "duplicate_suppressed",
                    "recommended_next_action": "none",
                    "message": "duplicate publish blocked by repository idempotency key",
                },
            )

        try:
            result = self.adapters.publish_segment(normalized_segment_id, payload, job_id=self.job_id)
        except Exception as error:
            self.repositories.delete_publish_key(self.job_id, normalized_segment_id, effective_destination)
            return PublishResult(
                "failed",
                "publish.failed",
                {
                    "provider": "youtube",
                    "operation": "publish_segment",
                    "category": "blocking",
                    "idempotency_outcome": "unknown",
                    "recommended_next_action": "retry_later",
                    "error_code": "adapter_unhandled_error",
                    "message": f"publish adapter error:{type(error).__name__}",
                },
            )
        if result.category == "success":
            event_type = (
                "publish.dedup_blocked"
                if result.idempotency_outcome == "duplicate_suppressed"
                else "publish.completed"
            )
            status = "blocked" if event_type == "publish.dedup_blocked" else "published"
            return PublishResult(status, event_type, result.payload)

        self.repositories.delete_publish_key(self.job_id, normalized_segment_id, effective_destination)
        return PublishResult("failed", "publish.failed", result.payload)
