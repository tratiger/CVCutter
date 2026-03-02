"""Program-entry normalization from ordered PDF text blocks."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from cvcutter.domain.models.metadata import ProgramEntry

if TYPE_CHECKING:
    from cvcutter.domain.services.types import PdfTextBlock

_NUMBERED_ENTRY_PATTERN = re.compile(
    r"^\s*(?:(\d+)[\.\)\-、]|\[(\d+)\]|第\s*(\d+)\s*番)\s*(.*)$",
)
_COMPOSER_TITLE_PATTERN = re.compile(
    r"^\s*(?P<composer>[^:/]{1,80})\s*[:/]\s*(?P<title>.+)$",
)
_COMPOSER_PREFIXES = ("作曲", "composer")
_PERFORMER_PREFIXES = ("演奏", "出演", "奏者", "performer")


def normalize_program_entries(text_blocks: list[PdfTextBlock]) -> list[ProgramEntry]:
    """Normalize ordered PDF text blocks into deterministic ProgramEntry records."""
    sorted_blocks = sorted(text_blocks, key=lambda block: (block.page_number, block.block_index))
    entries: list[ProgramEntry] = []
    current_lines: list[str] = []
    current_order: int | None = None
    next_order = 1

    def flush_current_entry() -> None:
        nonlocal current_lines, current_order, next_order
        if not current_lines:
            return

        order = current_order if current_order is not None else next_order
        piece_title, composer, performers = _extract_entry_fields(current_lines)
        raw_text = "\n".join(current_lines).strip()
        if raw_text:
            entry_index = len(entries) + 1
            entries.append(
                ProgramEntry(
                    id=f"program-{order:03d}-{entry_index:03d}",
                    order_number=order,
                    piece_title=piece_title or raw_text.splitlines()[0],
                    composer=composer,
                    performer_names=performers,
                    ensemble=None,
                    instrument=None,
                    raw_text=raw_text,
                ),
            )
            next_order = max(next_order, order + 1)

        current_lines = []
        current_order = None

    for block in sorted_blocks:
        for raw_line in block.text.splitlines():
            line = raw_line.strip()
            if not line:
                continue

            numbered = _NUMBERED_ENTRY_PATTERN.match(line)
            if numbered:
                flush_current_entry()
                order_text = numbered.group(1) or numbered.group(2) or numbered.group(3)
                current_order = max(1, int(order_text)) if order_text is not None else next_order
                body = numbered.group(4).strip()
                if body:
                    current_lines.append(body)
                continue

            if not current_lines:
                current_order = current_order or next_order
            current_lines.append(line)

    flush_current_entry()
    return entries


def _extract_entry_fields(lines: list[str]) -> tuple[str, str | None, list[str]]:
    piece_title: str | None = None
    composer: str | None = None
    performers: list[str] = []

    for line in lines:
        normalized = _normalize_space(line)
        lower = normalized.casefold()

        if _has_prefixed_field(lower, _COMPOSER_PREFIXES):
            composer = _value_after_separator(normalized)
            continue
        if _has_prefixed_field(lower, _PERFORMER_PREFIXES):
            performers.extend(_split_names(_value_after_separator(normalized)))
            continue
        if piece_title is None:
            piece_title = normalized

    if piece_title is None:
        piece_title = _normalize_space(lines[0]) if lines else "Unknown Piece"

    if composer is None:
        match = _COMPOSER_TITLE_PATTERN.match(piece_title)
        if match:
            composer = _normalize_space(match.group("composer"))
            piece_title = _normalize_space(match.group("title"))

    unique_performers: list[str] = []
    seen: set[str] = set()
    for name in performers:
        normalized = _normalize_space(name)
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        unique_performers.append(normalized)

    return piece_title, composer, unique_performers


def _has_prefixed_field(text: str, prefixes: tuple[str, ...]) -> bool:
    return any(re.match(rf"^{re.escape(prefix)}\s*:", text) for prefix in prefixes)


def _value_after_separator(text: str) -> str:
    if ":" in text:
        return _normalize_space(re.split(r"\s*:\s*", text, maxsplit=1)[1])
    return _normalize_space(text)


def _split_names(text: str) -> list[str]:
    if not text:
        return []
    return [part.strip() for part in re.split(r"[、,/&・]+", text) if part.strip()]


def _normalize_space(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("\uFF1A", ":")).strip()
