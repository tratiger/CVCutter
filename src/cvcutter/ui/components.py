from typing import Callable, Optional

import flet as ft


class FilePickerRow(ft.Row):
    def __init__(self, label: str, on_change: Callable[[str], None], is_dir: bool = False, file_types: Optional[list] = None):
        super().__init__()
        self.label = label
        self.on_change = on_change
        self.is_dir = is_dir
        self.file_types = file_types or []

        self.text_field = ft.TextField(label=self.label, expand=True, read_only=True)
        self.picker = ft.FilePicker()

        btn_text = "Select Folder" if is_dir else "Select File"

        self.controls = [
            self.text_field,
            ft.ElevatedButton(btn_text, on_click=self._on_click, icon="folder_open") # type: ignore
        ] # type: ignore

    def did_mount(self):
        if self.page:
            self.page.overlay.append(self.picker)
            self.page.update()

    async def _on_click(self, e):
        if self.is_dir:
            result = await self.picker.get_directory_path() # type: ignore
            if result:
                self.text_field.value = str(result)
                self.on_change(str(result))
        else:
            result = await self.picker.pick_files(allowed_extensions=self.file_types) # type: ignore
            if result and len(result) > 0:
                path = result[0].path
                if path:
                    self.text_field.value = str(path)
                    self.on_change(str(path))
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
            ft.Row([self.btn_prev, self.btn_next], alignment=ft.MainAxisAlignment.SPACE_BETWEEN) # type: ignore
        ] # type: ignore

    def set_content(self, controls: list[ft.Control]):
        self.content_area.controls = controls # type: ignore

    def set_can_next(self, can_next: bool):
        self.btn_next.disabled = not can_next
        self.update()
