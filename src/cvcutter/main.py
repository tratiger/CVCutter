"""CVCutter application entry point.

Initializes logging, runs legacy migration if needed, and launches the Flet UI.
"""

from __future__ import annotations

import sys


def main() -> None:
    """Application entry point.

    1. Initialize structured logging
    2. Run legacy config/state migration if needed
    3. Launch Flet application
    """
    # Phase 1 stub — will be wired to presentation/app.py in US5
    print("CVCutter starting...")

    try:
        from cvcutter.infrastructure.logging.structured_logger import init_logging

        init_logging()
    except ImportError:
        pass  # Logging not yet implemented

    try:
        from cvcutter.application.migration_service import MigrationService

        MigrationService().migrate_if_needed()
    except ImportError:
        pass  # Migration not yet implemented

    try:
        from cvcutter.presentation.app import launch

        launch()
    except ImportError:
        print("Presentation layer not yet implemented. Exiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
