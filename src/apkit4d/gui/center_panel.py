"""
Central column of the main window: the 3D view on top, the playback bar at the bottom.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


class CenterPanel(QWidget):
    """
    Column with a replaceable view and the playback bar.

    The view is a placeholder until the 3D view is plugged in with `set_view`.
    """

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("central_column")

        placeholder = QLabel("Open a .czi file to start (File > Open)")
        placeholder.setObjectName("central_placeholder")
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._view: QWidget = placeholder

        self._layout = QVBoxLayout(self)
        self._layout.addWidget(self._view, stretch=1)

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
