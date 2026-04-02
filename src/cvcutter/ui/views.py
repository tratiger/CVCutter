import threading

import flet as ft

from cvcutter.core.orchestrator import PipelineOrchestrator
from cvcutter.data.models import Project
from cvcutter.ui.components import FilePickerRow, WizardStep
from cvcutter.utils.logger import logger


class AppView(ft.Container):
    def __init__(self, orchestrator: PipelineOrchestrator, page: ft.Page):
        super().__init__()
        self.orchestrator = orchestrator
        self._page_ref = page
        self.expand = True

        # State
        self.current_project = Project(name="New Project")
        self.current_step_index = 0

        # UI
        self.main_area = ft.Container(expand=True, padding=20)
        self.content = self.main_area

        self._build_steps()
        self._show_step(0)

    def _build_steps(self):
        self.steps = [
            self._build_setup_step(),
            self._build_audio_sync_step(),
            self._build_analysis_step(),
            self._build_mapping_step(),
            self._build_render_step()
        ]

    def _show_step(self, index: int):
        if 0 <= index < len(self.steps):
            self.current_step_index = index
            self.main_area.content = self.steps[index]
            self._page_ref.update()

    def _next_step(self, e=None):
        self.orchestrator.session.add(self.current_project)
        self.orchestrator.session.commit()
        self._show_step(self.current_step_index + 1)

    def _prev_step(self, e=None):
        self._show_step(self.current_step_index - 1)

    # --- Step 1: Setup ---
    def _build_setup_step(self):
        step = WizardStep("Project Setup", on_next=self._next_step)

        name_input = ft.TextField(label="Project Name", value=str(self.current_project.name),
                                  on_change=lambda e: setattr(self.current_project, 'name', e.control.value))

        vid_picker = FilePickerRow("Video File", lambda p: setattr(self.current_project, 'video_path', p), file_types=["mp4", "mov", "mkv"])
        aud_picker = FilePickerRow("Mic Audio File", lambda p: setattr(self.current_project, 'audio_path', p), file_types=["wav", "mp3", "m4a"])
        pdf_picker = FilePickerRow("PDF Program (Optional)", lambda p: setattr(self.current_project, 'pdf_path', p), file_types=["pdf"])
        out_picker = FilePickerRow("Output Directory", lambda p: setattr(self.current_project, 'output_dir', p), is_dir=True)

        step.set_content([name_input, vid_picker, aud_picker, pdf_picker, out_picker])
        return step

    # --- Step 2: Audio Sync ---
    def _build_audio_sync_step(self):
        step = WizardStep("Audio Synchronization", on_next=self._next_step, on_prev=self._prev_step)

        self.offset_input = ft.TextField(label="Offset (seconds)", value="0.0")
        self.vid_vol = ft.Slider(min=0, max=1.0, value=0.2, label="Video Volume")
        self.mic_vol = ft.Slider(min=0, max=1.0, value=0.8, label="Mic Volume")

        status_text = ft.Text("")

        def run_sync(e):
            step.set_can_next(False)
            status_text.value = "Processing... (Check logs)"
            self._page_ref.update()

            def _worker():
                try:
                    self.orchestrator.sync_and_mix_audio(
                        self.current_project,
                        float(str(self.offset_input.value)),
                        float(self.vid_vol.value or 0.2),
                        float(self.mic_vol.value or 0.8)
                    )
                    status_text.value = "Success! Mixed audio applied."
                except Exception as ex:
                    logger.error(ex)
                    status_text.value = f"Error: {ex}"
                finally:
                    step.set_can_next(True)
                    self._page_ref.update()

            threading.Thread(target=_worker).start()

        sync_btn = ft.ElevatedButton("Sync & Mix Audio", on_click=run_sync)

        step.set_content([
            ft.Text("Adjust volume levels and start mix."),
            ft.Text("Video Track Volume"), self.vid_vol,
            ft.Text("Mic Track Volume"), self.mic_vol,
            self.offset_input,
            sync_btn,
            status_text
        ])
        return step

    # --- Step 3: Analysis ---
    def _build_analysis_step(self):
        step = WizardStep("Video Analysis", on_next=self._next_step, on_prev=self._prev_step)

        status_text = ft.Text("")
        self.segments = []

        def run_analysis(e):
            step.set_can_next(False)
            status_text.value = "Analyzing clapping and bowing... This will take a while."
            self._page_ref.update()

            def _worker():
                try:
                    self.segments = self.orchestrator.analyze_video(self.current_project)
                    status_text.value = f"Found {len(self.segments)} potential segments."
                except Exception as ex:
                    logger.error(ex)
                    status_text.value = f"Error: {ex}"
                finally:
                    step.set_can_next(True)
                    self._page_ref.update()

            threading.Thread(target=_worker).start()

        analyze_btn = ft.ElevatedButton("Run Analysis", on_click=run_analysis)

        step.set_content([
            ft.Text("Analyze video to find performance cuts automatically."),
            analyze_btn,
            status_text
        ])
        return step

    # --- Step 4: Mapping ---
    def _build_mapping_step(self):
        step = WizardStep("Metadata Mapping", on_next=self._next_step, on_prev=self._prev_step)

        api_key_input = ft.TextField(label="Gemini API Key (for PDF)", password=True)
        status_text = ft.Text("")

        def run_mapping(e):
            step.set_can_next(False)
            status_text.value = "Generating mapping..."
            self._page_ref.update()

            def _worker():
                try:
                    segs = self.segments if hasattr(self, 'segments') and self.segments else [(0.0, 10.0)]
                    self.orchestrator.generate_mapping(self.current_project, segs, str(api_key_input.value))
                    status_text.value = f"Successfully mapped {len(self.current_project.performances)} items."
                except Exception as ex:
                    logger.error(ex)
                    status_text.value = f"Error: {ex}"
                finally:
                    step.set_can_next(True)
                    self._page_ref.update()

            threading.Thread(target=_worker).start()

        map_btn = ft.ElevatedButton("Generate Mapping", on_click=run_mapping)

        step.set_content([
            api_key_input,
            map_btn,
            status_text
        ])
        return step

    # --- Step 5: Render & Upload ---
    def _build_render_step(self):
        def on_finish(e):
            # In Flet 0.21.2+ closing the window programmatically can be done like this:
            self._page_ref.window.destroy() # type: ignore

        step = WizardStep("Render & Upload", on_next=on_finish, on_prev=self._prev_step)

        status_text = ft.Text("")
        telop_checkbox = ft.Checkbox(label="Apply Telop", value=True)

        def run_render(e):
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

        render_btn = ft.ElevatedButton("Start Render & Upload", on_click=run_render)

        step.set_content([
            telop_checkbox,
            render_btn,
            status_text
        ])
        return step
