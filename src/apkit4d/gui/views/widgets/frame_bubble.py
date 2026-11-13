"""
Bubble that tells which frame the mouse is over, drawn by the slider just above its groove.

It is drawn inside the slider and not in a window of its own, because the position and the life of a
separate window depend on the window system: on some of them it cannot be moved after it appears, and it
disappears when the user clicks somewhere else.
"""

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QFontMetrics, QPainter, QPalette, QPolygonF

from apkit4d.gui.constants import appearance

ColorRole = QPalette.ColorRole


def make_bubble_font(base: QFont) -> QFont:
    """
    Return the font of the bubble.

    Args:
        base: The font of the widget, which gives the family.
    """
    font = QFont(base)
    font.setPointSizeF(appearance.BUBBLE_FONT_POINTS)
    font.setWeight(QFont.Weight.DemiBold)
    return font


def paint_bubble(
    painter: QPainter,
    palette: QPalette,
    font: QFont,
    text: str,
    tip: QPointF,
    limits: tuple[float, float],
) -> None:
    """
    Draw a bubble with `text` above `tip`, with its pointer touching `tip`.

    The bubble is the inverse of the window, so it stands out in every theme. It stays between the two
    limits, and when it has to move to do so, the pointer keeps pointing at `tip`.

    Args:
        painter: Painter of the widget where the bubble is drawn.
        palette: Palette that gives the colors.
        font: Font of the text, from `make_bubble_font`.
        text: What to say.
        tip: Point that the pointer touches.
        limits: Smallest and largest horizontal position that the bubble can cover.
    """
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    width = QFontMetrics(font).horizontalAdvance(text) + 2 * appearance.BUBBLE_PADDING
    left = min(max(tip.x() - width / 2, limits[0]), limits[1] - width)
    top = tip.y() - appearance.BUBBLE_POINTER_HEIGHT - appearance.BUBBLE_HEIGHT
    body = QRectF(left, top, width, appearance.BUBBLE_HEIGHT)

    painter.setBrush(palette.color(ColorRole.WindowText))
    painter.drawRoundedRect(body, appearance.BUBBLE_RADIUS, appearance.BUBBLE_RADIUS)

    half = appearance.BUBBLE_POINTER_WIDTH / 2
    margin = appearance.BUBBLE_RADIUS + half
    x = min(max(tip.x(), body.left() + margin), body.right() - margin)
    base = body.bottom() - 0.5  # overlaps the body, so that there is no seam
    painter.drawPolygon(QPolygonF([QPointF(x - half, base), QPointF(x + half, base), QPointF(x, tip.y())]))

    painter.setFont(font)
    painter.setPen(palette.color(ColorRole.Window))
    painter.drawText(body, Qt.AlignmentFlag.AlignCenter, text)
    painter.restore()
