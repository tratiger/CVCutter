"""SQLite-backed music dictionary lookup adapter."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from cvcutter.domain.services.music_lookup import MusicLookupService
from cvcutter.domain.services.types import MusicLookupMatch


class SqliteMusicLookup(MusicLookupService):
    """Lookup music metadata from a bundled SQLite dictionary."""

    def __init__(self, db_path: Path | None = None, *, table_name: str = "music_dictionary") -> None:
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
            raise ValueError("table_name must contain only letters, numbers, and underscores.")
        self._db_path = Path(db_path) if db_path is not None else Path(__file__).with_name("music_lookup.db")
        self._table_name = table_name

    def lookup(
        self,
        title: str,
        composer: str | None = None,
        performers: list[str] | None = None,
    ) -> list[MusicLookupMatch]:
        if not self.is_available() or not title.strip():
            return []
        query = (
            f"SELECT work_id, title, composer, performers, score "
            f"FROM {self._table_name} "
            "WHERE lower(title) LIKE lower(?) "
            "ORDER BY score DESC, title ASC "
            "LIMIT 10"
        )
        params: list[str] = [f"%{title.strip()}%"]
        if composer and composer.strip():
            query = (
                f"SELECT work_id, title, composer, performers, score "
                f"FROM {self._table_name} "
                "WHERE lower(title) LIKE lower(?) AND lower(coalesce(composer, '')) LIKE lower(?) "
                "ORDER BY score DESC, title ASC "
                "LIMIT 10"
            )
            params = [f"%{title.strip()}%", f"%{composer.strip()}%"]

        try:
            with sqlite3.connect(self._db_path) as connection:
                rows = connection.execute(query, params).fetchall()
        except sqlite3.Error:
            return []

        performer_filters = [name.strip() for name in performers or [] if name.strip()]
        revision = self.dictionary_revision()
        matches: list[MusicLookupMatch] = []
        for row in rows:
            row_performers = _split_performers(row[3])
            if performer_filters and not _has_performer_overlap(row_performers, performer_filters):
                continue
            matches.append(
                MusicLookupMatch(
                    work_id=str(row[0]),
                    title=str(row[1]),
                    composer=_optional_text(row[2]),
                    performers=row_performers,
                    score=_clamp(float(row[4]) if row[4] is not None else 0.0),
                    dictionary_revision=revision,
                ),
            )
        return matches

    def is_available(self) -> bool:
        if not self._db_path.exists():
            return False
        try:
            with sqlite3.connect(self._db_path) as connection:
                row = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (self._table_name,),
                ).fetchone()
            return row is not None
        except sqlite3.Error:
            return False

    def dictionary_revision(self) -> str:
        if not self._db_path.exists():
            return "missing"
        timestamp = int(self._db_path.stat().st_mtime)
        return f"sqlite:{self._db_path.name}:{timestamp}"


def _split_performers(value: object) -> list[str]:
    if value is None:
        return []
    text = str(value).strip()
    if not text:
        return []
    for separator in ("|", ";", "、"):
        text = text.replace(separator, ",")
    return [part.strip() for part in text.split(",") if part.strip()]


def _has_performer_overlap(candidates: list[str], filters: list[str]) -> bool:
    folded_candidates = [candidate.casefold() for candidate in candidates]
    for name in filters:
        folded = name.casefold()
        if any(folded in candidate or candidate in folded for candidate in folded_candidates):
            return True
    return False


def _optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))
