"""
Main window of the ApKit4D desktop application.

The window only lets the user choose a .czi file and announces it with the
`file_opened` signal. Reading the file and showing the volume are done by whoever
connects to that signal (the loader and the 3D view).
"""

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QLabel, QMainWindow

APP_NAME: str = "ApKit4D"
CZI_SUFFIX: str = ".czi"


class MainWindow(QMainWindow):
    """
    Application window with a File menu, a central area and a status bar.

    The central area holds a placeholder until the 3D view is added.

    Signals:
        file_opened: Emitted with the path of a .czi file once it has been accepted.
    """

    file_opened = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        placeholder = QLabel("Open a .czi file to start (File > Open)")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setCentralWidget(placeholder)

        self._build_file_menu()
        self.statusBar().showMessage("No file open")

    def _build_file_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")

        open_action = QAction("&Open...", self)
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._choose_file)
        menu.addAction(open_action)

        menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut(QKeySequence("Ctrl+Q"))
        quit_action.triggered.connect(self.close)
        menu.addAction(quit_action)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open a .czi file", "", "CZI files (*.czi)")
        if path:
            self.open_file(Path(path))

    def open_file(self, path: Path) -> bool:
        """
        Accept `path` if it is an existing .czi file and announce it.

        Args:
            path: File chosen by the user.

        Returns:
            True if the file was accepted and `file_opened` was emitted, False otherwise.
        """
        if path.suffix.lower() != CZI_SUFFIX:
            self.statusBar().showMessage(f"Not a .czi file: {path.name}")
            return False
        if not path.is_file():
            self.statusBar().showMessage(f"File not found: {path}")
            return False
        self.setWindowTitle(f"{path.name} - {APP_NAME}")
        self.statusBar().showMessage(str(path))
        self.file_opened.emit(path)
        return True
