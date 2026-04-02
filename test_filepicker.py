
import flet as ft

from cvcutter.ui.components import FilePickerRow


def main(page: ft.Page):
    def on_change(val):
        print(f"Selected: {val}")

    row = FilePickerRow("Test", on_change, is_dir=False)
    page.add(row)

    print("Success: FilePickerRow instantiates and mounts correctly.")

    # auto close
    page.window.destroy()

if __name__ == "__main__":
    ft.app(target=main)
