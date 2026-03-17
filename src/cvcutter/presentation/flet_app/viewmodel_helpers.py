from __future__ import annotations

import json
from pathlib import Path


_LOCALIZATION_FILE = Path(__file__).parent / "localization" / "ja_jp.json"


def localized(key: str) -> str:
    catalog = json.loads(_LOCALIZATION_FILE.read_text(encoding="utf-8"))
    return str(catalog.get(key, key))
