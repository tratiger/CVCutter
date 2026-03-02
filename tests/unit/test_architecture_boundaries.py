"""Architecture boundary tests (T008).

Validates the constitution requirement (CA-001) that the domain package has
ZERO imports from infrastructure, presentation, or external service SDKs.
The domain layer communicates with the outside world exclusively through
Protocol-based interfaces defined in domain/services/.

These tests use AST parsing to inspect import statements without executing code.
"""

from __future__ import annotations

import ast
import importlib
import pkgutil
from pathlib import Path
from typing import Any

import pytest

SRC_ROOT = Path(__file__).resolve().parent.parent.parent / "src"
DOMAIN_PKG = SRC_ROOT / "cvcutter" / "domain"
INFRA_PKG = SRC_ROOT / "cvcutter" / "infrastructure"
PRESENTATION_PKG = SRC_ROOT / "cvcutter" / "presentation"
APPLICATION_PKG = SRC_ROOT / "cvcutter" / "application"

# Packages the domain must NEVER import from
FORBIDDEN_DOMAIN_IMPORTS = {
    "cvcutter.infrastructure",
    "cvcutter.presentation",
    # External service SDKs that must not leak into domain
    "flet",
    "google",
    "googleapiclient",
    "google_auth_oauthlib",
    "google.auth",
    "google.generativeai",
    "ultralytics",
    "whisper",
    "onnxruntime",
    "pyinstaller",
    "PyInstaller",
    "customtkinter",
    "moviepy",
    "imageio_ffmpeg",
    "imageio",
    "subprocess",  # domain should not use subprocess
    "ffmpeg",
}

# Scientific runtime libs allowed in domain (per architecture rules)
ALLOWED_DOMAIN_EXTERNAL = {
    "numpy",
    "np",
    "scipy",
    "librosa",
    "cv2",  # OpenCV for type annotations
}


def _collect_python_files(pkg_dir: Path) -> list[Path]:
    """Recursively collect all .py files under a package directory."""
    return list(pkg_dir.rglob("*.py"))


def _extract_imports(file_path: Path) -> list[str]:
    """Extract all import module names from a Python source file using AST."""
    source = file_path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source, filename=str(file_path))
    except SyntaxError:
        return []

    imports: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append(node.module)
    return imports


class TestDomainBoundary:
    """Domain layer must not import from infrastructure or presentation."""

    def test_domain_has_no_infrastructure_imports(self) -> None:
        """Domain modules must not import from cvcutter.infrastructure."""
        violations: list[str] = []
        for py_file in _collect_python_files(DOMAIN_PKG):
            imports = _extract_imports(py_file)
            for imp in imports:
                for forbidden in FORBIDDEN_DOMAIN_IMPORTS:
                    if imp == forbidden or imp.startswith(f"{forbidden}."):
                        rel = py_file.relative_to(SRC_ROOT)
                        violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            f"Domain boundary violation(s):\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_domain_has_no_presentation_imports(self) -> None:
        """Domain modules must not import from cvcutter.presentation."""
        violations: list[str] = []
        for py_file in _collect_python_files(DOMAIN_PKG):
            imports = _extract_imports(py_file)
            for imp in imports:
                if imp.startswith("cvcutter.presentation"):
                    rel = py_file.relative_to(SRC_ROOT)
                    violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            f"Domain→Presentation violation(s):\n" + "\n".join(f"  - {v}" for v in violations)
        )

    def test_domain_services_only_use_domain_types(self) -> None:
        """Domain service protocols must only reference domain and shared types."""
        services_dir = DOMAIN_PKG / "services"
        if not services_dir.exists() or not list(services_dir.glob("*.py")):
            pytest.skip("Domain services not yet created")

        violations: list[str] = []
        for py_file in _collect_python_files(services_dir):
            imports = _extract_imports(py_file)
            for imp in imports:
                if imp.startswith("cvcutter.infrastructure") or imp.startswith(
                    "cvcutter.presentation"
                ):
                    rel = py_file.relative_to(SRC_ROOT)
                    violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            f"Domain services boundary violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestApplicationBoundary:
    """Application layer must not import from presentation."""

    def test_application_has_no_presentation_imports(self) -> None:
        """Application modules must not import from cvcutter.presentation."""
        py_files = _collect_python_files(APPLICATION_PKG)
        if not py_files or all(f.name == "__init__.py" for f in py_files):
            pytest.skip("Application package not yet created")

        violations: list[str] = []
        for py_file in _collect_python_files(APPLICATION_PKG):
            imports = _extract_imports(py_file)
            for imp in imports:
                if imp.startswith("cvcutter.presentation"):
                    rel = py_file.relative_to(SRC_ROOT)
                    violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            f"Application→Presentation violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestInfrastructureBoundary:
    """Infrastructure adapters must not bypass domain protocols."""

    def test_infrastructure_does_not_import_application(self) -> None:
        """Infrastructure must not import from application layer."""
        py_files = _collect_python_files(INFRA_PKG)
        if not py_files or all(f.name == "__init__.py" for f in py_files):
            pytest.skip("Infrastructure package not yet created")

        violations: list[str] = []
        for py_file in _collect_python_files(INFRA_PKG):
            imports = _extract_imports(py_file)
            for imp in imports:
                if imp.startswith("cvcutter.application"):
                    rel = py_file.relative_to(SRC_ROOT)
                    violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            f"Infrastructure→Application violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )

    def test_infrastructure_does_not_import_presentation(self) -> None:
        """Infrastructure must not import from presentation layer."""
        py_files = _collect_python_files(INFRA_PKG)
        if not py_files or all(f.name == "__init__.py" for f in py_files):
            pytest.skip("Infrastructure package not yet created")

        violations: list[str] = []
        for py_file in _collect_python_files(INFRA_PKG):
            imports = _extract_imports(py_file)
            for imp in imports:
                if imp.startswith("cvcutter.presentation"):
                    rel = py_file.relative_to(SRC_ROOT)
                    violations.append(f"{rel}: imports '{imp}'")

        assert violations == [], (
            f"Infrastructure→Presentation violation(s):\n"
            + "\n".join(f"  - {v}" for v in violations)
        )


class TestModuleSizePolicy:
    """All source modules must stay under 1000 lines (CA-007/SC-009)."""

    def test_no_module_exceeds_1000_lines(self) -> None:
        """Every .py file under src/ must be ≤1000 lines."""
        violations: list[tuple[str, int]] = []
        for py_file in SRC_ROOT.rglob("*.py"):
            line_count = len(py_file.read_text(encoding="utf-8").splitlines())
            if line_count > 1000:
                rel = py_file.relative_to(SRC_ROOT)
                violations.append((str(rel), line_count))

        assert violations == [], (
            f"Module size violation(s) (>1000 lines):\n"
            + "\n".join(f"  - {path}: {count} lines" for path, count in violations)
        )
