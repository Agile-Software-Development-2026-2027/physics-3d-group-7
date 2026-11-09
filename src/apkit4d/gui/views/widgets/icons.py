"""
Icons of the playback bar, drawn with vector shapes so that they are sharp at any size and take the
color that they are given, which makes them follow the theme.
"""

from enum import Enum

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygonF

_BOX = 20.0  # the icons are designed in a square of this size and scaled to the size that is asked
_STROKE = 1.8


class Icon(Enum):
    """The icons that a button can show."""

    PREVIOUS = "previous"
    NEXT = "next"
    PLAY = "play"
    PAUSE = "pause"


def paint_icon(painter: QPainter, icon: Icon, area: QRectF, color: QColor) -> None:
    """
    Draw `icon` filling `area`.

    Args:
        painter: Painter of the widget that shows the icon.
        icon: What to draw.
        area: Square where the icon is drawn.
        color: Color of the icon.
    """
    painter.save()
    painter.translate(area.topLeft())
    painter.scale(area.width() / _BOX, area.height() / _BOX)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(
        QPen(color, _STROKE, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
    )
    painter.setBrush(color)
    if icon in (Icon.PREVIOUS, Icon.NEXT):
        _paint_step(painter, pointing_left=icon is Icon.PREVIOUS)
    elif icon is Icon.PLAY:
        painter.drawPolygon(QPolygonF([QPointF(6.5, 4), QPointF(16, 10), QPointF(6.5, 16)]))
    elif icon is Icon.PAUSE:
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(QRectF(5.2, 4, 3.6, 12), 1.2, 1.2)
        painter.drawRoundedRect(QRectF(11.2, 4, 3.6, 12), 1.2, 1.2)
    painter.restore()


def _paint_step(painter: QPainter, *, pointing_left: bool) -> None:
    """A triangle with a bar at its tip, the symbol of "one frame back" and "one frame forward"."""
    direction = -1 if pointing_left else 1
    middle = _BOX / 2
    triangle = QPolygonF(
        [
            QPointF(middle - direction * 5, 4.5),
            QPointF(middle + direction * 5, 10),
            QPointF(middle - direction * 5, 15.5),
        ]
    )
    painter.drawPolygon(triangle)
    painter.drawLine(QPointF(middle + direction * 6.8, 4.5), QPointF(middle + direction * 6.8, 15.5))
