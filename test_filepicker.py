import flet as ft

from cvcutter.ui.components import FilePickerRow


def main(page: ft.Page):
    print("Testing FilePickerRow...")
    row = FilePickerRow("Test", lambda x: print(x), is_dir=False)
    page.add(row)
    print("Mounted FilePickerRow")
    page.window_close()

ft.app(target=main)
