from pathlib import Path

import pytest

from cvcutter.application.services.cleanup_service import cleanup_artifact


def test_cleanup_retention_protects_audit() -> None:
    result = cleanup_artifact("audit:event")
    assert result.event_type == "cleanup.rejected"
    assert result.target_class == "protected_minimal_audit"
    assert result.reason == "policy_protected"


def test_cleanup_deletes_selected_non_audit_artifact(tmp_path: Path) -> None:
    artifact = tmp_path / "scratch.log"
    artifact.write_text("temporary", encoding="utf-8")
    result = cleanup_artifact(str(artifact), managed_root=tmp_path)
    assert result.event_type == "cleanup.performed"
    assert not artifact.exists()


def test_cleanup_rejects_out_of_scope_paths(tmp_path: Path) -> None:
    managed_root = tmp_path / "managed"
    managed_root.mkdir()
    out_of_scope = tmp_path / "outside.log"
    out_of_scope.write_text("keep", encoding="utf-8")

    result = cleanup_artifact(str(out_of_scope), managed_root=managed_root)

    assert result.event_type == "cleanup.rejected"
    assert result.target_class == "deletable_artifact"
    assert result.reason == "policy_protected"
    assert out_of_scope.exists()


def test_cleanup_rejects_relative_traversal_paths(tmp_path: Path) -> None:
    managed_root = tmp_path / "managed"
    managed_root.mkdir()
    out_of_scope = tmp_path / "outside-relative.log"
    out_of_scope.write_text("keep", encoding="utf-8")

    result = cleanup_artifact(str(Path("..") / out_of_scope.name), managed_root=managed_root)

    assert result.event_type == "cleanup.rejected"
    assert result.target_class == "deletable_artifact"
    assert result.reason == "policy_protected"
    assert out_of_scope.exists()


def test_cleanup_rejects_when_managed_root_is_not_configured(tmp_path: Path) -> None:
    artifact = tmp_path / "scratch.log"
    artifact.write_text("temporary", encoding="utf-8")

    result = cleanup_artifact(str(artifact))

    assert result.event_type == "cleanup.rejected"
    assert result.target_class == "deletable_artifact"
    assert result.reason == "policy_protected"
    assert artifact.exists()


def test_cleanup_rejects_when_filesystem_delete_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    artifact = tmp_path / "locked.log"
    artifact.write_text("locked", encoding="utf-8")

    def _raise_permission(*_args, **_kwargs) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "unlink", _raise_permission)
    result = cleanup_artifact(str(artifact), managed_root=tmp_path)

    assert result.event_type == "cleanup.rejected"
    assert result.target_class == "deletable_artifact"
    assert result.reason == "delete_failed"
    assert artifact.exists()
