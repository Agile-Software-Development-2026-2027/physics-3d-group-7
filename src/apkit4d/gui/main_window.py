"""
Main window of the ApKit4D desktop application.

The window has three columns: controls on the left, the 3D view with its playback bar
in the center, controls on the right. It only lets the user choose a .czi file and
announces it with the `file_opened` signal. Reading the file and showing the volume
are done by whoever connects to that signal (the loader and the 3D view).
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QMainWindow, QWidget

from apkit4d.gui.center_panel import CenterPanel
from apkit4d.gui.left_panel import LeftPanel
from apkit4d.gui.right_panel import RightPanel

APP_NAME: str = "ApKit4D"
CZI_SUFFIX: str = ".czi"


class MainWindow(QMainWindow):
    """
    Application window with a File menu, three columns and a status bar.

    The central column holds a placeholder until the 3D view is added with `set_view`.
    Every component has an object name, so tests can find it with `findChild` and
    simulate the user.

    Signals:
        file_opened: Emitted with the path of a .czi file once it has been accepted.
    """

    file_opened = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1200, 800)

        self._left = LeftPanel()
        self._center = CenterPanel()
        self._right = RightPanel()
        self._build_columns()

        self._build_file_menu()
        self.statusBar().setObjectName("status_bar")
        self.statusBar().showMessage("No file open")

    @property
    def left_panel(self) -> LeftPanel:
        """Left column, where controls can be added."""
        return self._left

    @property
    def right_panel(self) -> RightPanel:
        """Right column, where controls can be added."""
        return self._right

    def set_view(self, view: QWidget) -> None:
        """
        Put `view` in the center of the window, in place of the placeholder.

        Args:
            view: Widget that fills the central column (the 3D view).
        """
        self._center.set_view(view)

    def _build_columns(self) -> None:
        container = QWidget()
        container.setObjectName("central_area")
        layout = QHBoxLayout(container)
        layout.addWidget(self._left)
        layout.addWidget(self._center, stretch=1)
        layout.addWidget(self._right)
        self.setCentralWidget(container)

    def _build_file_menu(self) -> None:
        menu = self.menuBar().addMenu("&File")
        menu.setObjectName("file_menu")

        open_action = QAction("&Open...", self)
        open_action.setObjectName("open_action")
        open_action.setShortcut(QKeySequence("Ctrl+O"))
        open_action.triggered.connect(self._choose_file)
        menu.addAction(open_action)

        menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setObjectName("quit_action")
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
