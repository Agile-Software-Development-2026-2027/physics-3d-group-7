"""
Central column of the main window: the 3D view on top, the playback bar at the bottom.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from apkit4d.gui.playback_bar import PlaybackBar


class CenterPanel(QWidget):
    """
    Column with a replaceable view and the playback bar.

    The view is a placeholder until the 3D view is plugged in with `set_view`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("center_panel")

        placeholder = QLabel("Open a .czi dile to start (File > Open)")
        placeholder.setObjectName("center_placeholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._view: QWidget = placeholder
        self._playback_bar = PlaybackBar()

        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._view, stretch=1)
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
        index = self._layout.indexOf(self._view)
        self._layout.removeWidget(self._view)
        self._view.setParent(None)
        self._view.deleteLater()
        self._layout.insertWidget(index, view, stretch=1)
        self._view = view
