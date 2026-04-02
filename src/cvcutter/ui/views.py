import datetime
import threading
from pathlib import Path

import flet as ft

from cvcutter.core.orchestrator import PipelineOrchestrator
from cvcutter.data.models import Project
from cvcutter.ui.components import FilePickerRow
from cvcutter.utils.logger import logger


class AppView(ft.Row):
    def __init__(self, orchestrator: PipelineOrchestrator, page: ft.Page):
        super().__init__()
        self.orchestrator = orchestrator
        self._page_ref = page
        self.expand = True

        # State
        default_name = f"New Project {datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}"
        self.current_project = Project(name=default_name, output_dir=str(Path.home() / "Videos"))
        self.segments = []
        self.api_key = ""

        # UI
        self.main_content = ft.Container(expand=True, padding=20)

        self.rail = ft.NavigationRail(
            selected_index=0,
            label_type=ft.NavigationRailLabelType.ALL,
            min_width=150,
            min_extended_width=250,
            extended=True,
            destinations=[
                ft.NavigationRailDestination(icon=ft.icons.VIDEO_SETTINGS, label="1. 動画処理"),
                ft.NavigationRailDestination(icon=ft.icons.PREVIEW, label="2. プレビュー & 紐付け"),
                ft.NavigationRailDestination(icon=ft.icons.UPLOAD, label="3. アップロード"),
                ft.NavigationRailDestination(icon=ft.icons.SETTINGS, label="設定"),
            ],
            on_change=self._on_rail_change,
        )

        self.controls = [
            self.rail,
            ft.VerticalDivider(width=1),
            self.main_content
        ]

        self._build_views()
        self._update_main_content(0)

    def _on_rail_change(self, e):
        self._update_main_content(e.control.selected_index)

    def _update_main_content(self, index: int):
        self.main_content.content = self.views[index]
        self._page_ref.update()

    def _build_views(self):
        self.views = [
            self._build_process_view(),
            self._build_mapping_view(),
            self._build_upload_view(),
            self._build_settings_view()
        ]

    def _save_project_state(self):
        """Helper to save the current project state without violating unique constraints."""
        session = self.orchestrator.session
        # Check if project with same name already exists in DB
        existing = session.query(Project).filter_by(name=str(self.current_project.name)).first()

        if existing is not None and getattr(existing, "id", None) != self.current_project.id:
            # Merge with existing
            self.current_project.id = existing.id
            self.current_project = session.merge(self.current_project)
        else:
            session.add(self.current_project)

        session.commit()

    def _build_process_view(self):
        vid_picker = FilePickerRow("Video File", lambda p: setattr(self.current_project, 'video_path', p), file_types=["mp4", "mov", "mkv", "mts", "MTS"])
        aud_picker = FilePickerRow("Mic Audio File", lambda p: setattr(self.current_project, 'audio_path', p), file_types=["wav", "mp3", "m4a"])

        offset_input = ft.TextField(label="Sync Offset (seconds)", value="0.0")
        vid_vol = ft.Slider(min=0, max=1.0, value=0.2, label="Video Volume")
        mic_vol = ft.Slider(min=0, max=1.0, value=0.8, label="Mic Volume")
        status_text = ft.Text("")

        def run_all_process(e):
            if str(self.current_project.video_path) in ["None", ""]:
                status_text.value = "Error: Please select a Video File first."
                self._page_ref.update()
                return

            try:
                self._save_project_state()
            except Exception as ex:
                status_text.value = f"Database Error: {ex} (Change project name in Settings)"
                self._page_ref.update()
                return

            status_text.value = "1/2: Mixing Audio..."
            self._page_ref.update()

            def _worker():
                try:
                    if str(self.current_project.audio_path) not in ["None", ""]:
                        self.orchestrator.sync_and_mix_audio(
                            self.current_project,
                            float(str(offset_input.value)),
                            float(vid_vol.value or 0.2),
                            float(mic_vol.value or 0.8)
                        )

                    status_text.value = "2/2: Analyzing Video (Detecting cuts)..."
                    self._page_ref.update()

                    self.segments = self.orchestrator.analyze_video(self.current_project)
                    status_text.value = f"Processing Complete! Found {len(self.segments)} segments."
                except Exception as ex:
                    logger.error(ex)
                    status_text.value = f"Error: {ex}"
                finally:
                    self._page_ref.update()

            threading.Thread(target=_worker).start()

        return ft.Column([
            ft.Text("Step 1: 動画の音声同期と自動カット解析", size=20, weight=ft.FontWeight.BOLD),
            vid_picker,
            aud_picker,
            ft.Divider(),
            ft.Text("Audio Settings", weight=ft.FontWeight.BOLD),
            ft.Row([offset_input, ft.Column([ft.Text("Video Vol"), vid_vol]), ft.Column([ft.Text("Mic Vol"), mic_vol])]),
            ft.ElevatedButton("Start Processing", on_click=run_all_process),
            status_text
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def _build_mapping_view(self):
        pdf_picker = FilePickerRow("PDF Program (Optional)", lambda p: setattr(self.current_project, 'pdf_path', p), file_types=["pdf"])
        status_text = ft.Text("")

        def run_mapping(e):
            try:
                self._save_project_state()
            except Exception as ex:
                status_text.value = f"Database Error: {ex}"
                self._page_ref.update()
                return

            status_text.value = "Generating mapping..."
            self._page_ref.update()

            def _worker():
                try:
                    segs = self.segments if hasattr(self, 'segments') and self.segments else [(0.0, 10.0)]
                    self.orchestrator.generate_mapping(self.current_project, segs, self.api_key)
                    status_text.value = f"Successfully mapped {len(self.current_project.performances)} items."
                except Exception as ex:
                    logger.error(ex)
                    status_text.value = f"Error: {ex}"
                finally:
                    self._page_ref.update()

            threading.Thread(target=_worker).start()

        return ft.Column([
            ft.Text("Step 2: プログラムプレビュー & 紐付け", size=20, weight=ft.FontWeight.BOLD),
            pdf_picker,
            ft.Text("※Gemini API Keyは設定タブで入力してください。"),
            ft.ElevatedButton("Generate Mapping", on_click=run_mapping),
            status_text
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def _build_upload_view(self):
        status_text = ft.Text("")
        telop_checkbox = ft.Checkbox(label="Apply Telop", value=True)

        def run_render(e):
            try:
                self._save_project_state()
            except Exception as ex:
                status_text.value = f"Database Error: {ex}"
                self._page_ref.update()
                return

            status_text.value = "Rendering clips..."
            self._page_ref.update()
            def _worker():
                try:
                    self.orchestrator.render_all(self.current_project, apply_telop=bool(telop_checkbox.value))
                    status_text.value = "Rendering complete! Starting upload..."
                    self._page_ref.update()
                    self.orchestrator.upload_pending(self.current_project)
                    status_text.value = "Upload complete!"
                except Exception as ex:
                    logger.error(ex)
                    status_text.value = f"Error: {ex}"
                finally:
                    self._page_ref.update()
            threading.Thread(target=_worker).start()

        return ft.Column([
            ft.Text("Step 3: 動画出力 & YouTubeアップロード", size=20, weight=ft.FontWeight.BOLD),
            telop_checkbox,
            ft.ElevatedButton("Start Render & Upload", on_click=run_render),
            status_text
        ], scroll=ft.ScrollMode.AUTO, expand=True)

    def _build_settings_view(self):
        name_input = ft.TextField(label="Project Name", value=str(self.current_project.name),
                                  on_change=lambda e: setattr(self.current_project, 'name', e.control.value))

        out_picker = FilePickerRow("Output Directory", lambda p: setattr(self.current_project, 'output_dir', p), is_dir=True)

        def set_api_key(e):
            self.api_key = e.control.value

        api_input = ft.TextField(label="Gemini API Key", password=True, on_change=set_api_key)

        return ft.Column([
            ft.Text("設定", size=20, weight=ft.FontWeight.BOLD),
            name_input,
            out_picker,
            api_input
        ], scroll=ft.ScrollMode.AUTO, expand=True)
