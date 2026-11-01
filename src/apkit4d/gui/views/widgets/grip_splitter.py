"""
Splitter whose handles are easy to grab.

The handle of a plain Qt splitter is a few pixels wide and hard to hit. Here it is a wider strip with
a thin line and, in the middle, a small grip with two arrows that show the direction of the drag.
The whole strip can be dragged, not only the grip, and it lights up while the mouse is over it or
is dragging it.
"""

from typing import override

from PySide6.QtCore import QEvent, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QEnterEvent, QMouseEvent, QPainter, QPaintEvent, QPalette, QPolygonF
from PySide6.QtWidgets import QSplitter, QSplitterHandle, QWidget

from apkit4d.gui.constants import appearance

ColorRole = QPalette.ColorRole


def _with_opacity(color: QColor, opacity: int) -> QColor:
    """Return a copy of `color` with the given opacity, from 0 (invisible) to 255 (solid)."""
    result = QColor(color)
    result.setAlpha(opacity)
    return result


class GripHandle(QSplitterHandle):
    """
    Handle with a line and a grip in the middle.

    The colors come from the palette, so the handle follows the theme. While the mouse is over the
    handle or is dragging it, it is painted with the highlight color.

    Args:
        orientation: Orientation of the splitter that owns the handle.
        parent: The splitter that owns the handle.
    """

    def __init__(self, orientation: Qt.Orientation, parent: QSplitter) -> None:
        super().__init__(orientation, parent)
        self._hovered = False
        self._pressed = False

    @property
    def is_highlighted(self) -> bool:
        """True while the mouse is over the handle or is dragging it."""
        return self._hovered or self._pressed

    @override
    def enterEvent(self, event: QEnterEvent) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    @override
    def leaveEvent(self, event: QEvent) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        self._pressed = True
        self.update()
        super().mousePressEvent(event)

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._pressed = False
        self.update()
        super().mouseReleaseEvent(event)

    @override
    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        line_color, grip_color, arrow_color = self._colors()

        across, along = self._sizes()
        middle = across // 2

        grip_length = min(appearance.GRIP_LENGTH, along)
        grip_thickness = min(appearance.GRIP_THICKNESS, across)
        grip_start = (along - grip_length) / 2
        grip_end = grip_start + grip_length

        # the line is interrupted by the grip, otherwise it would show through it
        line = appearance.HANDLE_LINE_WIDTH
        painter.fillRect(self._rect(middle - line // 2, 0, line, grip_start), line_color)
        painter.fillRect(self._rect(middle - line // 2, grip_end, line, along - grip_end), line_color)

        painter.setBrush(grip_color)
        painter.drawRoundedRect(
            self._rect(middle - grip_thickness // 2, grip_start, grip_thickness, grip_length),
            appearance.GRIP_RADIUS,
            appearance.GRIP_RADIUS,
        )

        painter.setBrush(arrow_color)
        painter.drawPolygon(self._arrow(middle, grip_start + grip_length / 2, direction=-1))
        painter.drawPolygon(self._arrow(middle, grip_start + grip_length / 2, direction=1))

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        """Colors of the line, of the grip and of the arrows, in this order."""
        palette = self.palette()
        if self.is_highlighted:
            accent = palette.color(ColorRole.Highlight)
            return accent, accent, palette.color(ColorRole.HighlightedText)
        ink = palette.color(ColorRole.WindowText)
        return (
            _with_opacity(ink, appearance.HANDLE_LINE_OPACITY),
            _with_opacity(ink, appearance.GRIP_OPACITY),
            _with_opacity(ink, appearance.GRIP_ARROW_OPACITY),
        )

    def _arrow(self, middle: float, center: float, direction: int) -> QPolygonF:
        """
        Triangle that points away from the line, across the strip.

        Args:
            middle: Position of the line across the strip.
            center: Position of the middle of the grip along the strip.
            direction: -1 for the arrow on the side of the first widget, 1 for the other one.
        """
        base = middle + direction * appearance.GRIP_ARROW_GAP / 2
        tip = base + direction * appearance.GRIP_ARROW_WIDTH
        half = appearance.GRIP_ARROW_HEIGHT / 2
        return QPolygonF(
            [self._point(tip, center), self._point(base, center - half), self._point(base, center + half)]
        )

    def _is_vertical_strip(self) -> bool:
        """True when the handle is a vertical strip, that is when the splitter puts widgets side by side."""
        return self.orientation() == Qt.Orientation.Horizontal

    def _sizes(self) -> tuple[int, int]:
        """Size of the handle across the strip (its thickness) and along it (its length)."""
        if self._is_vertical_strip():
            return self.width(), self.height()
        return self.height(), self.width()

    def _rect(self, across: float, along: float, thickness: float, length: float) -> QRectF:
        """Rectangle described by its position and size across and along the strip."""
        if self._is_vertical_strip():
            return QRectF(across, along, thickness, length)
        return QRectF(along, across, length, thickness)

    def _point(self, across: float, along: float) -> QPointF:
        """Point described by its position across and along the strip."""
        if self._is_vertical_strip():
            return QPointF(across, along)
        return QPointF(along, across)


class GripSplitter(QSplitter):
    """
    Splitter whose handles are `GripHandle`s, wide enough to be grabbed easily.

    Args:
        orientation: Horizontal puts the widgets side by side, vertical one above the other.
        parent: Qt parent of the splitter.
    """

    def __init__(self, orientation: Qt.Orientation, parent: QWidget | None = None) -> None:
        super().__init__(orientation, parent)
        self.setHandleWidth(appearance.HANDLE_WIDTH)

    @override
    def createHandle(self) -> QSplitterHandle:
        return GripHandle(self.orientation(), self)
