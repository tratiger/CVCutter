import flet as ft
import asyncio

async def main(page: ft.Page):
    fp = ft.FilePicker()
    page.overlay.append(fp)
    page.update()

    print("Mounted FilePicker")
    page.window.destroy()

ft.app(main)
