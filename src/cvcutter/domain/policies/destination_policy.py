from __future__ import annotations

APPROVED_DESTINATIONS = {"youtube"}
APPROVED_PROVIDERS = {"google_forms", "gemini", "youtube"}


def ensure_destination_allowed(provider: str, destination: str) -> None:
    if provider not in APPROVED_PROVIDERS:
        raise ValueError("provider not approved")
    if destination not in APPROVED_DESTINATIONS:
        raise ValueError("destination not approved")
