"""
Center column of the main window: the 3D view on top, the playback bar at the bottom.
"""

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QStackedWidget, QVBoxLayout, QWidget

from apkit4d.gui.constants import names
from apkit4d.gui.views.playback.playback_bar import PlaybackBar
from apkit4d.gui.views.widgets.file_drop_surface import FileDropSurface


class CenterPanel(QWidget):
    """
    Column with a replaceable view and the playback bar.

    The drop surface is shown until a file is loaded and a 3D view is plugged in with `set_view`.
    """

    file_dropped = Signal(Path)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName(names.CENTER_PANEL)

        self._file_loaded = False
        self._view: QWidget | None = None
        self._drop_surface = FileDropSurface()
        self._drop_surface.file_dropped.connect(self.file_dropped)
        self._view_stack = QStackedWidget()  # stack: drag-and-grop surface below, viewport above
        self._view_stack.addWidget(self._drop_surface)
        self._playback_bar = PlaybackBar()

        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._view_stack, stretch=1)
        self._layout.addWidget(self._playback_bar)

    @property
    def playback_bar(self) -> PlaybackBar:
        """The bar at the bottom of the column."""
        return self._playback_bar

    def set_view(self, view: QWidget) -> None:
        """
        Put `view` above the playback bar, in place of the current one.

        Args:
            view: Widget that fills the column (the 3D view).
        """
        if view is self._view:
            return
        if self._view is not None:
            self._view_stack.removeWidget(self._view)
            self._view.setParent(None)
            self._view.deleteLater()
        self._view = view
        self._view_stack.addWidget(view)
        self._show_active_surface()

    def set_file_loaded(self, loaded: bool) -> None:
        """Show the viewport only while a file is loaded."""
        self._file_loaded = loaded
        self._show_active_surface()

    def _show_active_surface(self) -> None:
        if self._file_loaded and self._view is not None:
            self._view_stack.setCurrentWidget(self._view)
        else:
            self._view_stack.setCurrentWidget(self._drop_surface)
