"""
Base class of the side columns of the main window.
"""

from PySide6.QtWidgets import QVBoxLayout, QWidget


class SidePanel(QWidget):
    """
    Column where controls are stacked from the top.

    The panel has no fixed width: the splitter of the main window sets the initial one,
    lets the user resize it down to `SIDE_PANEL_MIN_WIDTH` and collapse it completely.

    Args:
        object_name: Name used by the tests to find the panel.
    """

    def __init__(self, object_name: str) -> None:
        super().__init__()
        self.setObjectName(object_name)
        self.setMinimumWidth(120)  # SIDE_PANEL_MIN_WIDTH
        self._layout = QVBoxLayout(self)
        self._layout.addStretch()

    def add_control(self, widget: QWidget) -> None:
        """
        Add `widget` below the controls already in the panel.

        Args:
            widget: Button or other control to show.
        """
        self._layout.insertWidget(self._layout.count() - 1, widget)  # above the final stretch
