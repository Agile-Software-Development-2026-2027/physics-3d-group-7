"""
Little bubble that floats above the slider and tells which frame the mouse is over.
"""

from typing import override

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetrics, QGuiApplication, QPainter, QPaintEvent, QPalette, QPolygonF
from PySide6.QtWidgets import QWidget

from apkit4d.gui.constants import appearance

ColorRole = QPalette.ColorRole


class FrameBubble(QWidget):
    """
    Bubble with a text and a pointer, shown above a point of the screen.

    It is a window of its own, like the tooltips, because it has to float over the 3D view while the bar
    is only a few pixels tall. The mouse goes through it, so it never gets in the way.

    Args:
        parent: A widget of the window that the bubble belongs to.
    """

    def __init__(self, parent: QWidget) -> None:
        flags = (
            Qt.WindowType.ToolTip
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowTransparentForInput
        )
        super().__init__(parent, flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        font = QFont(self.font())
        font.setPointSizeF(appearance.BUBBLE_FONT_POINTS)
        font.setWeight(QFont.Weight.DemiBold)
        self.setFont(font)
        self._text = ""
        self._pointer_x = 0

    @property
    def text(self) -> str:
        """The text that the bubble shows."""
        return self._text

    def point_at(self, text: str, tip: QPoint) -> None:
        """
        Show `text` in a bubble above `tip`, with the pointer touching it.

        The bubble stays inside the screen. When it has to move to do so, the pointer keeps pointing at `tip`.

        Args:
            text: What to say.
            tip: Position on the screen, in global coordinates, that the pointer must touch.
        """
        self._text = text
        width = QFontMetrics(self.font()).horizontalAdvance(text) + 2 * appearance.BUBBLE_PADDING
        height = appearance.BUBBLE_HEIGHT + appearance.BUBBLE_POINTER_HEIGHT
        left = tip.x() - width // 2
        screen = QGuiApplication.screenAt(tip)
        if screen is not None:
            area = screen.availableGeometry()
            left = min(max(left, area.left()), area.right() - width + 1)
        self._pointer_x = tip.x() - left
        self.resize(width, height)
        self.move(left, tip.y() - height)
        self.update()
        self.show()

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        palette = self.palette()
        painter.setBrush(palette.color(ColorRole.WindowText))  # the bubble is the inverse of the window
        body = QRectF(0, 0, self.width(), appearance.BUBBLE_HEIGHT)
        painter.drawRoundedRect(body, appearance.BUBBLE_RADIUS, appearance.BUBBLE_RADIUS)

        half = appearance.BUBBLE_POINTER_WIDTH / 2
        margin = appearance.BUBBLE_RADIUS + half
        x = min(max(self._pointer_x, margin), self.width() - margin)
        base = appearance.BUBBLE_HEIGHT - 0.5  # overlaps the body, so that there is no seam
        painter.drawPolygon(
            QPolygonF(
                [
                    QPointF(x - half, base),
                    QPointF(x + half, base),
                    QPointF(x, appearance.BUBBLE_HEIGHT + appearance.BUBBLE_POINTER_HEIGHT),
                ]
            )
        )

        painter.setPen(palette.color(ColorRole.Window))
        painter.drawText(body, Qt.AlignmentFlag.AlignCenter, self._text)
