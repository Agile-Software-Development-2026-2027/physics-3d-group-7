"""
Main window of the ApKit4D desktop application.

The window has three columns, resizable with a splitter: controls on the left, the 3D view with its
playback bar in the center, controls on the right. It only lets the user choose a .czi file and
announces it with the `file_opened` signal. Reading the file and showing the volume are done by
whoever connects to that signal (the controller).
"""

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QFileDialog, QMainWindow, QMenu, QWidget

from apkit4d.gui.constants import appearance, application, names, shortcuts, texts
from apkit4d.gui.views.panels.center_panel import CenterPanel
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.widgets.grip_splitter import GripSplitter
from apkit4d.gui.views.widgets.playback_bar import PlaybackBar


class MainWindow(QMainWindow):
    """
    Application window with a File menu, three columns and a status bar.

    The center panel holds a placeholder until the 3D view is added with `set_view`. Every component
    has an object name, so tests can find it with `findChild` and simulate the user.

    Signals:
        file_opened: Emitted with the path of a .czi file once it has been accepted.
    """

    file_opened = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(application.APP_NAME)
        self.resize(appearance.WINDOW_WIDTH, appearance.WINDOW_HEIGHT)

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
            view: Widget that fills the center panel (the 3D view).
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
        if path.suffix.lower() != application.CZI_SUFFIX:
            self.statusBar().showMessage(texts.STATUS_NOT_CZI.format(name=path.name))
            return False
        if not path.is_file():
            self.statusBar().showMessage(texts.STATUS_NOT_FOUND.format(path=path))
            return False
        self.setWindowTitle(texts.WINDOW_TITLE_WITH_FILE.format(name=path.name, app=application.APP_NAME))
        self.statusBar().showMessage(str(path))
        self.file_opened.emit(path)
        return True

    def _build_columns(self) -> None:
        splitter = GripSplitter(Qt.Orientation.Horizontal)
        splitter.setObjectName(names.COLUMNS_SPLITTER)

        columns = (self._left, self._center, self._right)
        settings = zip(columns, appearance.COLUMN_COLLAPSIBLE, appearance.COLUMN_STRETCH, strict=True)
        for index, (column, collapsible, stretch) in enumerate(settings):
            splitter.addWidget(column)
            splitter.setCollapsible(index, collapsible)
            splitter.setStretchFactor(index, stretch)
        splitter.setSizes(list(appearance.COLUMN_SIZES))

        self.setCentralWidget(splitter)

    def _build_file_menu(self) -> None:
        menu = self.menuBar().addMenu(texts.MENU_FILE)
        menu.setObjectName(names.FILE_MENU)
        self._add_action(menu, names.OPEN_ACTION, texts.ACTION_OPEN, shortcuts.OPEN, self._choose_file)
        menu.addSeparator()
        self._add_action(menu, names.QUIT_ACTION, texts.ACTION_QUIT, shortcuts.QUIT, self.close)

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
        status_bar.setObjectName(names.STATUS_BAR)
        status_bar.showMessage(texts.STATUS_NO_FILE)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, texts.FILE_DIALOG_TITLE, "", texts.FILE_DIALOG_FILTER)
        if path:
            self.open_file(Path(path))
