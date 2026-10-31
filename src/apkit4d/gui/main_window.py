"""
Main window of the ApKit4D desktop application.

The window has three columns, resizable with a splitter: controls on the left, the 3D view
with its playback bar in the center, controls on the right. It only lets the user choose a
.czi file and announces it with the `file_opened` signal. Reading the file and showing the
volume are done by whoever connects to that signal (the controller).
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu, QSplitter, QWidget

from apkit4d.gui import constants
from apkit4d.gui.center_panel import CenterPanel
from apkit4d.gui.left_panel import LeftPanel
from apkit4d.gui.playback_bar import PlaybackBar
from apkit4d.gui.right_panel import RightPanel


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
        self.setWindowTitle(constants.APP_NAME)
        self.resize(constants.WINDOW_WIDTH, constants.WINDOW_HEIGHT)

        self._left = LeftPanel()
        self._center = CenterPanel()
        self._right = RightPanel()

        self._build_columns()
        self._build_file_menu()
        self._build_status_bar()

    @property
    def left_panel(self) -> LeftPanel:
        """Left column, where controls can be added."""
        return self._left

    @property
    def right_panel(self) -> RightPanel:
        """Right column, where controls can be added."""
        return self._right

    @property
    def playback_bar(self) -> PlaybackBar:
        """Bar under the 3D view, to be connected by the controller."""
        return self._center.playback_bar

    def set_view(self, view: QWidget) -> None:
        """
        Put `view` in the center of the window, in place of the placeholder.

        Args:
            view: Widget that fills the central column (the 3D view).
        """
        self._center.set_view(view)

    def open_file(self, path: Path) -> bool:
        """
        Accept `path` if it is an existing .czi file and announce it.

        Args:
            path: File chosen by the user.

        Returns:
            True if the file was accepted and `file_opened` was emitted, False otherwise.
        """
        if path.suffix.lower() != constants.CZI_SUFFIX:
            self.statusBar().showMessage(constants.TEXT_STATUS_NOT_CZI.format(name=path.name))
            return False
        if not path.is_file():
            self.statusBar().showMessage(constants.TEXT_STATUS_NOT_FOUND.format(path=path))
            return False
        self.setWindowTitle(
            constants.TEXT_WINDOW_TITLE_WITH_FILE.format(name=path.name, app=constants.APP_NAME)
        )
        self.statusBar().showMessage(str(path))
        self.file_opened.emit(path)
        return True

    def _build_columns(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName(constants.NAME_COLUMNS_SPLITTER)

        columns = (self._left, self._center, self._right)
        settings = zip(columns, constants.COLUMN_COLLAPSIBLE, constants.COLUMN_STRETCH, strict=True)
        for index, (column, collapsible, stretch) in enumerate(settings):
            splitter.addWidget(column)
            splitter.setCollapsible(index, collapsible)
            splitter.setStretchFactor(index, stretch)
        splitter.setSizes(list(constants.COLUMN_SIZES))

        self.setCentralWidget(splitter)

    def _build_file_menu(self) -> None:
        menu = self.menuBar().addMenu(constants.TEXT_MENU_FILE)
        menu.setObjectName(constants.NAME_FILE_MENU)
        self._add_action(
            menu,
            constants.NAME_OPEN_ACTION,
            constants.TEXT_ACTION_OPEN,
            constants.SHORTCUT_OPEN,
            self._choose_file,
        )
        menu.addSeparator()
        self._add_action(
            menu,
            constants.NAME_QUIT_ACTION,
            constants.TEXT_ACTION_QUIT,
            constants.SHORTCUT_QUIT,
            self.close,
        )

    # I had to write it in this format, otherwise RUFF complains
    def _add_action(
        self, menu: QMenu, name: str, text: str, shortcut: str, slot: Callable[..., object]
    ) -> None:
        action = QAction(text, self)
        action.setObjectName(name)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)

    def _build_status_bar(self) -> None:
        status_bar = self.statusBar()
        status_bar.setObjectName(constants.NAME_STATUS_BAR)
        status_bar.showMessage(constants.TEXT_STATUS_NO_FILE)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, constants.TEXT_FILE_DIALOG_TITLE, "", constants.TEXT_FILE_DIALOG_FILTER
        )
        if path:
            self.open_file(Path(path))
