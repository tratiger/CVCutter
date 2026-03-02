from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path


def compute_file_hash(file_path: Path, algorithm: str = "sha256") -> str:
    """Compute a file hash using streaming reads for memory efficiency."""
    hasher = hashlib.new(algorithm)

    with file_path.open("rb") as file_obj:
        for chunk in iter(lambda: file_obj.read(64 * 1024), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_config_hash(config: dict[str, Any]) -> str:
    """Compute a deterministic SHA-256 hash for a config dictionary."""
    serialized = json.dumps(config, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()
