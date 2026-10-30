"""
Entry point of the desktop GUI.

The `gui` command of the CLI calls `run`. Nothing in the core imports this package.
"""

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from apkit4d.gui.main_window import MainWindow


def run(path: Path | None = None) -> int:
    """
    Show the main window and run the Qt event loop until the window is closed.

    Args:
        path: Optional .czi file to open at startup.

    Returns:
        Exit code of the Qt event loop, 0 when the window is closed normally.
    """
    app = QApplication.instance() or QApplication(sys.argv)
    window = MainWindow()
    # the loader and the 3D view will be connected to window.file_opened here
    window.show()
    if path is not None:
        window.open_file(path)
    return app.exec()
