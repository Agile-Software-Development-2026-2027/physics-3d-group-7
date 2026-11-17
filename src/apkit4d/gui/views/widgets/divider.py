"""
Thin vertical line that separates two groups of controls.
"""

from typing import override

from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QWidget

from apkit4d.gui.constants import appearance
from apkit4d.gui.views.widgets.colors import mix

ColorRole = QPalette.ColorRole


class Divider(QWidget):
    """
    One pixel wide line, in a color between the window and the text, so it is quiet in every theme.

    Args:
        parent: Qt parent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setFixedSize(1, appearance.DIVIDER_HEIGHT)

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        palette = self.palette()
        color = mix(
            palette.color(ColorRole.Window), palette.color(ColorRole.WindowText), appearance.BORDER_MIX
        )
        painter = QPainter(self)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        painter.drawRect(self.rect())
