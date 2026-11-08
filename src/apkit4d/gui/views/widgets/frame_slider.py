"""
Slider to choose a frame: a thin groove that fills up with the accent color and a round handle.
"""

from typing import override

from PySide6.QtCore import QEvent, QPoint, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QHideEvent, QMouseEvent, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QSlider, QStyle, QWidget

from apkit4d.gui.constants import appearance, texts
from apkit4d.gui.views.widgets.colors import mix
from apkit4d.gui.views.widgets.frame_bubble import FrameBubble

ColorRole = QPalette.ColorRole


class FrameSlider(QSlider):
    """
    Horizontal slider painted with the colors of the theme.

    Pressing anywhere on the groove jumps to that value, and the value follows the mouse while the
    button is held down. A standard Qt slider would move by a whole page instead.

    While the mouse is over the groove, a marker shows the frame under it and a bubble above the slider
    says its number, counting from 1, as the frame counter does.

    Args:
        parent: Qt parent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.setFixedHeight(appearance.SLIDER_HEIGHT)
        self.setMouseTracking(True)  # to follow the mouse also when no button is pressed
        self._hover: int | None = None
        self._bubble: FrameBubble | None = None

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)

        palette = self.palette()
        window = palette.color(ColorRole.Window)
        ink = palette.color(ColorRole.WindowText)
        accent = palette.color(ColorRole.Highlight)
        enabled = self.isEnabled()

        pad = appearance.SLIDER_PADDING
        groove = appearance.SLIDER_GROOVE_HEIGHT
        top = self.height() / 2 - groove / 2
        x = self._position_of(self.value())
        radius = groove / 2

        groove_color = mix(window, ink, appearance.GROOVE_MIX if enabled else appearance.DISABLED_GROOVE_MIX)
        painter.setBrush(groove_color)
        painter.drawRoundedRect(QRectF(pad, top, self.width() - 2 * pad, groove), radius, radius)
        if enabled:
            painter.setBrush(accent)
            painter.drawRoundedRect(QRectF(pad, top, x - pad, groove), radius, radius)
        if self._hover is not None and enabled:
            self._paint_marker(painter, self._position_of(self._hover), ink)

        ring = accent if enabled else mix(window, ink, appearance.DISABLED_RING_MIX)
        painter.setPen(QPen(ring, appearance.SLIDER_HANDLE_RING))
        painter.setBrush(Qt.GlobalColor.white if enabled else window)
        painter.drawEllipse(
            QPointF(x, self.height() / 2),
            appearance.SLIDER_HANDLE_RADIUS,
            appearance.SLIDER_HANDLE_RADIUS,
        )

    @override
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton or not self.isEnabled():
            event.ignore()
            return
        self.setSliderDown(True)
        self.setValue(self._value_at(event.position().x()))
        self._follow(event.position().x())
        event.accept()

    @override
    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        self._follow(event.position().x())
        if self.isSliderDown():
            self.setValue(self._value_at(event.position().x()))
        event.accept()

    @override
    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.isSliderDown():
            self.setSliderDown(False)
            event.accept()

    @override
    def leaveEvent(self, event: QEvent) -> None:
        self._stop_following()
        super().leaveEvent(event)

    @override
    def hideEvent(self, event: QHideEvent) -> None:
        self._stop_following()
        super().hideEvent(event)

    @override
    def changeEvent(self, event: QEvent) -> None:
        if event.type() == QEvent.Type.EnabledChange and not self.isEnabled():
            self._stop_following()
        super().changeEvent(event)

    def _follow(self, x: float) -> None:
        """Show the marker and the bubble for the frame under the horizontal position `x`."""
        frame = self._value_at(x)
        if frame == self._hover:
            return
        self._hover = frame
        self.update()
        groove_top = self.height() / 2 - appearance.SLIDER_GROOVE_HEIGHT / 2
        tip = self.mapToGlobal(QPoint(self._position_of(frame), int(groove_top) - appearance.BUBBLE_GAP))
        if self._bubble is None:
            self._bubble = FrameBubble(self.window())
        self._bubble.point_at(texts.HOVER_FRAME.format(frame=frame + 1), tip)

    def _stop_following(self) -> None:
        if self._hover is not None:
            self._hover = None
            self.update()
        if self._bubble is not None:
            self._bubble.hide()

    def _paint_marker(self, painter: QPainter, x: int, ink: QColor) -> None:
        color = QColor(ink)
        color.setAlpha(appearance.HOVER_MARKER_OPACITY)
        painter.setPen(
            QPen(color, appearance.HOVER_MARKER_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        )
        middle = self.height() / 2
        half = appearance.HOVER_MARKER_HALF_HEIGHT
        painter.drawLine(QPointF(x, middle - half), QPointF(x, middle + half))

    def _span(self) -> int:
        return self.width() - 2 * appearance.SLIDER_PADDING

    def _position_of(self, value: int) -> int:
        """Horizontal position of the center of the handle for `value`."""
        return (
            QStyle.sliderPositionFromValue(self.minimum(), self.maximum(), value, self._span())
            + appearance.SLIDER_PADDING
        )

    def _value_at(self, x: float) -> int:
        """Value that corresponds to the horizontal position `x`."""
        return QStyle.sliderValueFromPosition(
            self.minimum(), self.maximum(), round(x) - appearance.SLIDER_PADDING, self._span()
        )
