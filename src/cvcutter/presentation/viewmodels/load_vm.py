"""Load screen view-model."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol


class LoadWorkflow(Protocol):
    """Application service contract for creating projects from UI input."""

    def create_project(
        self,
        *,
        project_name: str,
        video_files: list[Path],
        external_audio_file: Path | None,
        program_pdf_file: Path | None,
        form_csv_file: Path | None,
        form_remote_id: str | None,
        form_remote_sheet_id: str | None,
        output_directory: Path,
    ) -> Any:
        """Create and persist a project aggregate from load-screen inputs."""
        ...


@dataclass
class LoadViewModel:
    """State and commands for the file-loading workflow step."""

    workflow: LoadWorkflow
    output_directory: Path
    project_name: str = "新規プロジェクト"
    video_files: list[Path] = field(default_factory=list)
    external_audio_file: Path | None = None
    program_pdf_file: Path | None = None
    form_csv_file: Path | None = None
    form_remote_id: str | None = None
    form_remote_sheet_id: str | None = None
    validation_errors: list[str] = field(default_factory=list)

    @property
    def can_proceed(self) -> bool:
        """Return True when required inputs are currently valid."""
        return bool(self.video_files) and not self.validation_errors

    def add_videos(self, paths: list[Path]) -> None:
        """Append selected source videos while preserving unique order."""
        for path in paths:
            if path not in self.video_files:
                self.video_files.append(path)
        self.validate()

    def remove_video(self, index: int) -> None:
        """Remove one source video by list index."""
        if 0 <= index < len(self.video_files):
            self.video_files.pop(index)
        self.validate()

    def reorder_videos(self, from_index: int, to_index: int) -> None:
        """Move one source video to a new order position."""
        if not 0 <= from_index < len(self.video_files):
            raise ValueError("移動元インデックスが不正です。")
        if not 0 <= to_index < len(self.video_files):
            raise ValueError("移動先インデックスが不正です。")
        target = self.video_files.pop(from_index)
        self.video_files.insert(to_index, target)
        self.validate()

    def set_external_audio(self, path: Path | None) -> None:
        """Set optional external microphone audio source."""
        self.external_audio_file = path
        self.validate()

    def set_program_pdf(self, path: Path | None) -> None:
        """Set optional concert program PDF path."""
        self.program_pdf_file = path
        self.validate()

    def set_form_csv(self, path: Path | None) -> None:
        """Set optional form CSV path."""
        self.form_csv_file = path
        self.validate()

    def set_form_remote_source(self, form_id: str | None, sheet_id: str | None) -> None:
        """Set optional remote Google Form/Sheet identifiers."""
        self.form_remote_id = form_id or None
        self.form_remote_sheet_id = sheet_id or None
        self.validate()

    def validate(self) -> list[str]:
        """Validate current state and return error messages."""
        errors: list[str] = []
        if not self.project_name.strip():
            errors.append("プロジェクト名を入力してください。")
        if not self.video_files:
            errors.append("動画ファイルを1つ以上選択してください。")
        if not isinstance(self.output_directory, Path):
            errors.append("出力先フォルダーを設定してください。")
        self.validation_errors = errors
        return list(errors)

    def create_project(self) -> Any:
        """Validate input and delegate project creation to application workflow."""
        if self.validate():
            raise ValueError("入力内容に不備があります。")
        return self.workflow.create_project(
            project_name=self.project_name.strip(),
            video_files=list(self.video_files),
            external_audio_file=self.external_audio_file,
            program_pdf_file=self.program_pdf_file,
            form_csv_file=self.form_csv_file,
            form_remote_id=self.form_remote_id,
            form_remote_sheet_id=self.form_remote_sheet_id,
            output_directory=self.output_directory,
        )
