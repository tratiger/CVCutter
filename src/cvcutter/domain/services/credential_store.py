"""Protocol for credential persistence with safe display support.

Implementations are responsible for secure per-user storage semantics and
redacted summaries suitable for logs or diagnostics.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class CredentialStore(Protocol):
    """Port for credential storage and retrieval."""

    def load(self, service_name: str) -> dict[str, str] | None:
        """Load credentials for a service name, returning None when absent."""
        ...

    def save(self, service_name: str, credentials: dict[str, str]) -> None:
        """Persist credentials for a service with secure file-permission guarantees."""
        ...

    def delete(self, service_name: str) -> None:
        """Delete credentials associated with a service name."""
        ...

    def redacted_summary(self, service_name: str) -> dict[str, str]:
        """Return credential keys with redacted values for safe display/logging."""
        ...

