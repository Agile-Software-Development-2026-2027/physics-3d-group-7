"""
Entry point of the desktop GUI.

The `gui` command of the CLI calls `run`. Nothing in the core imports this package.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.visualization.viewport import Viewport


def _get_application() -> QApplication:
    """Return the running application, or create it. Qt allows only one."""
    existing = QApplication.instance()
    if isinstance(existing, QApplication):
        return existing
    return QApplication(sys.argv)


def run(path: Path | None = None) -> int:
    """
    Show the main window and run the Qt event loop until the window is closed.

    Args:
        path: Optional .czi file to open at startup.

    Returns:
        Exit code of the Qt event loop, 0 when the window is closed normally.
    """
    app = _get_application()
    window = MainWindow()
    viewport = Viewport()
    window.set_view(viewport)
    MainController(window, app, window, view=viewport)
    window.show()
    if path is not None:
        window.open_file(path)
    return app.exec()
