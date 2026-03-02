"""Module size enforcement tool.

Scans all Python source files under src/ and fails if any module exceeds
1000 lines of code (constitution CA-007 / SC-009 enforcement).

Usage:
    uv run python tools/check_module_size.py

Exit code 0: all modules within limit.
Exit code 1: one or more modules exceed limit.
"""

from __future__ import annotations

import sys
from pathlib import Path

MAX_LINES = 1000
SRC_ROOT = Path(__file__).resolve().parent.parent / "src"


def check_module_sizes() -> list[tuple[str, int]]:
    """Return list of (relative_path, line_count) for over-limit modules."""
    violations: list[tuple[str, int]] = []

    for py_file in SRC_ROOT.rglob("*.py"):
        line_count = len(py_file.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            rel_path = str(py_file.relative_to(SRC_ROOT.parent))
            violations.append((rel_path, line_count))

    return violations


def main() -> None:
    """Run module-size check and report results."""
    violations = check_module_sizes()

    if violations:
        print(f"❌ Module size violations (>{MAX_LINES} lines):")
        for path, count in sorted(violations):
            print(f"  {path}: {count} lines")
        sys.exit(1)
    else:
        total_files = sum(1 for _ in SRC_ROOT.rglob("*.py"))
        print(f"✓ All {total_files} modules within {MAX_LINES}-line limit.")
        sys.exit(0)


if __name__ == "__main__":
    main()
