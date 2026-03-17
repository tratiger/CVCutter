from __future__ import annotations

from dataclasses import dataclass

from cvcutter.domain.policies.destination_policy import ensure_destination_allowed


@dataclass(slots=True)
class AdapterResult:
    ok: bool
    payload: dict[str, object]
    retriable: bool = False


class ApprovedAdapters:
    def publish_segment(self, segment_id: str, metadata: dict[str, object]) -> AdapterResult:
        mandatory = {"title", "destination"}
        if not mandatory.issubset(metadata):
            return AdapterResult(False, {"error": "missing_publish_fields"})
        destination = str(metadata["destination"])
        try:
            ensure_destination_allowed("youtube", destination)
        except ValueError:
            return AdapterResult(False, {"error": "destination_not_allowed"})
        return AdapterResult(True, {"segment_id": segment_id})

    def fetch_form_responses(self, form_id: str) -> AdapterResult:
        return AdapterResult(True, {"form_id": form_id, "responses": []})

    def classify_content(self, text: str) -> AdapterResult:
        return AdapterResult(True, {"label": "concert", "input": text})
