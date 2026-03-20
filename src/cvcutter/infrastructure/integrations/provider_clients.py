from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol


class FormsClient(Protocol):
    def fetch(self, form_id: str, *, job_id: str) -> dict[str, object]:
        ...


class ClassifierClient(Protocol):
    def classify(self, text: str, *, job_id: str) -> dict[str, object]:
        ...


@dataclass(slots=True)
class DefaultFormsClient:
    def fetch(self, form_id: str, *, job_id: str) -> dict[str, object]:
        return {
            "schema_version": "2",
            "source_format": "json",
            "records": [
                {
                    "program_id": "P-AUTO-IMPORTED",
                    "segment_title": "Imported segment",
                    "performer_display_name": "Auto Imported Performer",
                    "publish_visibility": "public",
                    "description": "",
                    "tags": ["auto-imported", "google-forms"],
                }
            ],
        }


@dataclass(slots=True)
class DefaultClassifierClient:
    def classify(self, text: str, *, job_id: str) -> dict[str, object]:
        normalized = text.strip().lower()
        top_candidate = "encore" if "encore" in normalized else "unclassified"
        confidence_state = "confident" if top_candidate != "unclassified" else "no_confident_match"
        digest = hashlib.sha1(f"{job_id}:classifier".encode("utf-8")).hexdigest()
        return {
            "classification_reference_id": f"cls:{digest}",
            "top_candidate": top_candidate,
            "confidence_state": confidence_state,
        }
