from __future__ import annotations

from typing import Literal, TypedDict, NotRequired


PublishVisibility = Literal["public", "unlisted", "private"]
ClassificationStrategy = Literal["content_based", "timestamp_based"]


class MetadataRecord(TypedDict):
    program_id: str
    segment_title: str
    performer_display_name: str
    publish_visibility: PublishVisibility
    description: NotRequired[str]
    tags: NotRequired[list[str]]
    playlist_id: NotRequired[str]
    operator_note: NotRequired[str]


class RuntimeEventPayload(TypedDict, total=False):
    operation_id: str
    attempt: int
    stage: str
    state: str
    free_gb: int
    threshold_gb: int
    action_taken: str
