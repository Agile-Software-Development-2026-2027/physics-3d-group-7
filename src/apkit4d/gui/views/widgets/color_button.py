"""
Button that shows a color and lets the user choose another one with the color dialog of Qt.
"""

from PySide6.QtCore import QSize, Signal
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QColorDialog, QPushButton, QWidget

_SWATCH_SIZE = 14  # side of the square that shows the color, in pixels
_SWATCH_BORDER = "#808080"  # gray, so that the square is visible on light and dark buttons


class ColorButton(QPushButton):
    """
    Button with a square of its color and the hex code of the color, for example "#1f2023".

    Pressing it opens the color dialog. The button does not change its color by itself: it announces the
    choice with `color_chosen`, and whoever decides calls `set_color`.

    Args:
        dialog_title: Title of the color dialog.
        parent: Qt parent.

    Signals:
        color_chosen: Emitted with the hex code of the color chosen in the dialog.
    """

    color_chosen = Signal(str)

    def __init__(self, dialog_title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._dialog_title = dialog_title
        self._color = QColor()
        self.setIconSize(QSize(_SWATCH_SIZE, _SWATCH_SIZE))
        self.clicked.connect(self._choose)

    @property
    def color(self) -> str:
        """Hex code of the color that the button shows, empty until `set_color` is called."""
        return self._color.name() if self._color.isValid() else ""

    def set_color(self, color: str) -> None:
        """
        Show `color` on the button.

        Args:
            color: A color name or a hex code, for example "white" or "#1f2023".
        """
        self._color = QColor(color)
        swatch = QPixmap(self.iconSize())
        swatch.fill(self._color)
        painter = QPainter(swatch)
        painter.setPen(QColor(_SWATCH_BORDER))
        painter.drawRect(swatch.rect().adjusted(0, 0, -1, -1))
        painter.end()
        self.setIcon(QIcon(swatch))
        self.setText(self._color.name())

    def _choose(self) -> None:
        chosen = QColorDialog.getColor(self._color, self, self._dialog_title)
        if chosen.isValid():  # not valid when the dialog is closed without choosing
            self.color_chosen.emit(chosen.name())
