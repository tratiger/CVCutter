import flet as ft

from cvcutter.core.orchestrator import PipelineOrchestrator
from cvcutter.data.external import MetadataService
from cvcutter.data.models import get_engine, get_session_maker
from cvcutter.ui.views import AppView
from cvcutter.utils.logger import logger


def _app_target(page: ft.Page):
    logger.info("Starting CVCutter Application")
    page.title = "CVCutter"
    page.window_width = 800
    page.window_height = 600
    page.theme_mode = ft.ThemeMode.DARK

    # Initialize Core Services
    engine = get_engine()
    Session = get_session_maker(engine)
    session = Session()

    meta_service = MetadataService()
    orchestrator = PipelineOrchestrator(session, meta_service)

    # Mount View
    app_view = AppView(orchestrator, page)
    page.add(app_view)

def main():
    """CLI entry point."""
    ft.app(target=_app_target)

if __name__ == "__main__":
    main()
