import flet as ft
from typing import Callable, Optional

class FilePickerRow(ft.Row):
    def __init__(self, label: str, on_change: Callable[[str], None], is_dir: bool = False, file_types: Optional[list] = None):
        super().__init__()
        self.label = label
        self.on_change = on_change
        self.is_dir = is_dir
        self.file_types = file_types or []

        self.text_field = ft.TextField(label=self.label, expand=True, read_only=True)
        self.picker = ft.FilePicker(on_result=self._on_result)

        btn_text = "Select Folder" if is_dir else "Select File"

        self.controls = [
            self.picker,
            self.text_field,
            ft.ElevatedButton(btn_text, on_click=self._on_click, icon=ft.icons.FOLDER)
        ]

    def _on_click(self, e):
        if self.is_dir:
            self.picker.get_directory_path()
        else:
            self.picker.pick_files(allowed_extensions=self.file_types)

    def _on_result(self, e: ft.FilePickerResultEvent):
        if e.path and self.is_dir:
            self.text_field.value = e.path
            self.on_change(e.path)
        elif e.files and not self.is_dir:
            path = e.files[0].path
            if path:
                self.text_field.value = path
                self.on_change(path)
        self.update()

class WizardStep(ft.Column):
    def __init__(self, title: str, on_next: Callable, on_prev: Optional[Callable] = None, can_next: bool = True):
        super().__init__()
        self.expand = True
        self.title_text = ft.Text(title, size=24, weight=ft.FontWeight.BOLD)
        self.content_area = ft.Column(expand=True, scroll=ft.ScrollMode.AUTO)

        self.btn_prev = ft.ElevatedButton("Back", on_click=on_prev if on_prev else lambda e: None, disabled=on_prev is None)
        self.btn_next = ft.FilledButton("Next", on_click=on_next, disabled=not can_next)

        self.controls = [
            self.title_text,
            self.content_area,
            ft.Row([self.btn_prev, self.btn_next], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
        ]

    def set_content(self, controls: list[ft.Control]):
        self.content_area.controls = controls

    def set_can_next(self, can_next: bool):
        self.btn_next.disabled = not can_next
        self.update()
