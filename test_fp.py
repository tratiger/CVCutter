import flet as ft
import asyncio

async def main(page: ft.Page):
    print(type(page.services))
    fp = ft.FilePicker()

    try:
        page.services.append(fp)
        page.update()
        print("Mounted FilePicker in page.services")
    except Exception as e:
        print("Error mounting in page.services:", e)

    page.window.destroy()

ft.app(target=main)
