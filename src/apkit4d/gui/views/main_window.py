"""
Main window of the apkit4d desktop application.

The window has three columns, resizable with a splitter: controls on the left, the 3D view with its
playback bar in the center, controls on the right. It only lets the user choose a .czi file and
announces it with the `file_opened` signal. Reading the file and showing the volume are done by
whoever connects to that signal (the controller).
"""

from collections.abc import Callable
from pathlib import Path
from typing import override

from PySide6.QtCore import QEvent, QObject, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QApplication, QDockWidget, QFileDialog, QLabel, QMainWindow, QMenu, QWidget

from apkit4d.gui.constants import appearance, application, names, shortcuts, texts
from apkit4d.gui.views.panels.center_panel import CenterPanel
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.gui.views.panels.multi_file_panel import MultiFilePanel
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.playback.playback_bar import PlaybackBar
from apkit4d.gui.views.widgets.grip_splitter import GripSplitter
from apkit4d.visualization.fps_counter import FpsCounter


class MainWindow(QMainWindow):
    """
    Application window with a File menu, three columns and a status bar.

    The center panel holds a placeholder until the 3D view is added with `set_view`. Every component
    has an object name, so tests can find it with `findChild` and simulate the user.

    Signals:
        files_selected: Emitted with the paths selected for a new batch.
        files_added: Emitted with the paths selected to extend the batch.
        file_opened: Emitted with the path of a .czi file once it has been accepted.
        results_opened: Emitted with the path of the json of saved results chosen by the user.
        video_export_requested: Emitted when the user requests a video export.
    """

    files_selected = Signal(list)
    files_added = Signal(list)
    file_opened = Signal(Path)
    results_opened = Signal(Path)
    video_export_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(application.APP_NAME)
        self.resize(appearance.WINDOW_WIDTH, appearance.WINDOW_HEIGHT)

        self._left = LeftPanel()
        self._center = CenterPanel()
        self._right = RightPanel()

        self._qt_fps_ticker = FpsCounter(window_seconds=1.0)
        self._qt_frame_pending = False
        self._render_fps_provider: Callable[[], float] | None = None

        self._fps_timer = QTimer(self)
        self._fps_timer.setInterval(150)
        self._fps_timer.timeout.connect(self._update_fps_label)

        self._build_columns()
        self.multi_file_panel = MultiFilePanel()
        self._multi_file_dock = QDockWidget(texts.MULTI_FILE_TITLE, self)
        self._multi_file_dock.setObjectName("multiFileDock")
        self._multi_file_dock.setWidget(self.multi_file_panel)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, self._multi_file_dock)
        self._multi_file_dock.hide()
        self._multi_file_dock.visibilityChanged.connect(self._size_multi_file_dock_on_first_show)
        self._build_file_menu()
        self._build_view_menu()
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
        if hasattr(view, "render_fps"):
            self._render_fps_provider = lambda: float(view.render_fps)  # type: ignore

    def set_status(self, message: str) -> None:
        """
        Show `message` in the status bar.

        Args:
            message: Text to show.
        """
        self.statusBar().showMessage(message)

    def set_current_file(self, path: Path | None) -> None:
        """
        Show the name of the open file in the title of the window.

        Args:
            path: The open file, or None to show only the name of the application.
        """
        if path is None:
            self.setWindowTitle(application.APP_NAME)
        else:
            self.setWindowTitle(texts.WINDOW_TITLE_WITH_FILE.format(name=path.name, app=application.APP_NAME))

    def open_file(self, path: Path) -> bool:
        """
        Accept `path` if it is an existing .czi file and announce it.

        The window does not read the file: whoever receives `file_opened` does, and tells the window
        the outcome with `set_current_file` and `set_status`.

        Args:
            path: File chosen by the user.

        Returns:
            True if the file was accepted and `file_opened` was emitted, False otherwise.
        """
        if path.suffix.lower() != application.CZI_SUFFIX:
            self.set_status(texts.STATUS_NOT_CZI.format(name=path.name))
            return False
        if not path.is_file():
            self.set_status(texts.STATUS_NOT_FOUND.format(path=path))
            return False
        self.file_opened.emit(path)
        return True

    def choose_recording(self, name: str) -> Path | None:
        """
        Ask the user where the recording `name` is, when saved results cannot find it.

        Args:
            name: File name of the recording.

        Returns:
            The chosen file, or None if the user cancels.
        """
        path, _ = QFileDialog.getOpenFileName(
            self, texts.FIND_RECORDING_TITLE.format(name=name), "", texts.FILE_DIALOG_FILTER
        )
        return Path(path) if path else None

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
        self.open_files_action = self._add_action(
            menu, "openFilesAction", texts.MULTI_FILE_OPEN_ACTION, None, self._choose_files
        )
        self.add_files_action = self._add_action(
            menu, "addFilesAction", texts.MULTI_FILE_ADD_ACTION, None, self._choose_additional_files
        )
        self.add_files_action.setEnabled(False)
        self._add_action(
            menu,
            names.OPEN_RESULTS_ACTION,
            texts.ACTION_OPEN_RESULTS,
            shortcuts.OPEN_RESULTS,
            self._choose_results,
        )
        self._add_action(
            menu,
            names.EXPORT_VIDEO_ACTION,
            texts.ACTION_EXPORT_VIDEO,
            shortcuts.EXPORT_VIDEO,
            self.video_export_requested.emit,
        )
        menu.addSeparator()
        self._add_action(menu, names.QUIT_ACTION, texts.ACTION_QUIT, shortcuts.QUIT, self.close)

    def _build_view_menu(self) -> None:
        menu = self.menuBar().addMenu(texts.MENU_VIEW)
        menu.setObjectName(names.VIEW_MENU)

        menu.addAction(self._multi_file_dock.toggleViewAction())

        action = QAction(texts.ACTION_SHOW_FPS, self)
        action.setObjectName(names.SHOW_FPS_ACTION)
        action.setCheckable(True)
        action.setChecked(False)
        action.toggled.connect(self._on_show_fps_toggled)
        menu.addAction(action)

    def _build_status_bar(self) -> None:
        status_bar = self.statusBar()
        status_bar.setObjectName(names.STATUS_BAR)
        status_bar.showMessage(texts.STATUS_NO_FILE)

        self._fps_label = QLabel()
        self._fps_label.setObjectName(names.FPS_LABEL)
        self._fps_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        widest = texts.FPS_READOUT.format(qt_fps=999.9, render_fps=999.9)
        self._fps_label.setFixedWidth(self._fps_label.fontMetrics().horizontalAdvance(widest))
        self._fps_label.setVisible(False)
        status_bar.addPermanentWidget(self._fps_label)

    def _on_show_fps_toggled(self, enabled: bool) -> None:
        self._fps_label.setVisible(enabled)
        app = QApplication.instance()
        if enabled:
            self._qt_fps_ticker.reset()
            self._qt_frame_pending = False
            if app is not None:
                app.installEventFilter(self)
            self._update_fps_label()
            self._fps_timer.start()
        else:
            self._fps_timer.stop()
            self._qt_frame_pending = False
            if app is not None:
                app.removeEventFilter(self)

    def _update_fps_label(self) -> None:
        qt_fps = self._qt_fps_ticker.fps()
        render_fps = self._render_fps_provider() if self._render_fps_provider is not None else 0.0
        self._fps_label.setText(texts.FPS_READOUT.format(qt_fps=qt_fps, render_fps=render_fps))

    def _add_action(
        self, menu: QMenu, name: str, text: str, shortcut: str | None, slot: Callable[..., object]
    ) -> QAction:
        """Add a menu action with an optional shortcut and return it for later updates."""
        action = QAction(text, self)
        action.setObjectName(name)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, texts.FILE_DIALOG_TITLE, "", texts.FILE_DIALOG_FILTER)
        if path:
            self.open_file(Path(path))

    def show_multi_file_panel(self) -> None:
        """Show the batch panel when its queue is ready."""
        self._multi_file_dock.show()

    def _size_multi_file_dock_on_first_show(self, visible: bool) -> None:
        if visible:
            self._multi_file_dock.visibilityChanged.disconnect(self._size_multi_file_dock_on_first_show)
            self.resizeDocks([self._multi_file_dock], [180], Qt.Orientation.Vertical)

    def _choose_recordings(self, title: str) -> list[Path]:
        selected_filenames, _selected_filter = QFileDialog.getOpenFileNames(
            self, title, "", texts.FILE_DIALOG_FILTER
        )
        paths = []
        for filename in selected_filenames:
            paths.append(Path(filename))
        return paths

    def _choose_files(self) -> None:
        paths = self._choose_recordings(texts.MULTI_FILE_OPEN_DIALOG)
        if paths:
            self.files_selected.emit(paths)

    def _choose_additional_files(self) -> None:
        paths = self._choose_recordings(texts.MULTI_FILE_ADD_DIALOG)
        if paths:
            self.files_added.emit(paths)

    def _choose_results(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, texts.RESULTS_DIALOG_TITLE, "", texts.RESULTS_DIALOG_FILTER
        )
        if path:
            self.results_opened.emit(Path(path))

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if (
            self._fps_timer.isActive()
            and event.type() == QEvent.Type.Paint
            and watched is not self._fps_label
            and not self._qt_frame_pending
        ):
            self._qt_frame_pending = True
            QTimer.singleShot(0, self._commit_qt_frame)
        return super().eventFilter(watched, event)

    def _commit_qt_frame(self) -> None:
        self._qt_frame_pending = False
        if self._fps_timer.isActive():
            self._qt_fps_ticker.tick()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        self._fps_timer.stop()
        if (app := QApplication.instance()) is not None:
            app.removeEventFilter(self)
        super().closeEvent(event)
