"""
Button that shows an icon followed by a text, painted with the colors of the theme.
"""

from typing import override

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFontMetrics, QPainter, QPaintEvent
from PySide6.QtWidgets import QPushButton, QSizePolicy, QWidget

from apkit4d.gui.constants import appearance
from apkit4d.gui.views.widgets.colors import focus_pen, plain_button_colors
from apkit4d.gui.views.widgets.icons import Icon, paint_icon


class LabeledButton(QPushButton):
    """
    Rounded button with an icon and a text, as wide as its content needs.

    It can be made compact, and then it shows only the icon, in a square button.

    Args:
        icon: The icon to show before the text.
        text: The text of the button.
        parent: Qt parent.
    """

    _compact: bool = False  # a default of the class: a handler can run on an instance that Python has emptied

    def __init__(self, icon: Icon, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self._icon = icon
        self.setFixedHeight(appearance.ACTION_BUTTON_HEIGHT)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # the focus ring is for the keyboard, not for the mouse

    def set_compact(self, compact: bool) -> None:
        """
        Show only the icon, or the icon and the text.

        Args:
            compact: True to show only the icon.
        """
        if compact != self._compact:
            self._compact = compact
            self.updateGeometry()
            self.update()

    @override
    def sizeHint(self) -> QSize:
        if self._compact:
            return QSize(appearance.ACTION_BUTTON_HEIGHT, appearance.ACTION_BUTTON_HEIGHT)
        text_width = QFontMetrics(self.font()).horizontalAdvance(self.text())
        content = appearance.ACTION_ICON_SIZE + appearance.ACTION_ICON_GAP + text_width
        return QSize(2 * appearance.ACTION_BUTTON_PADDING + content, appearance.ACTION_BUTTON_HEIGHT)

    @override
    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        palette = self.palette()
        background, border, ink = plain_button_colors(
            palette, enabled=self.isEnabled(), down=self.isDown(), hovered=self.underMouse()
        )
        focused = self.hasFocus()
        inset = appearance.FOCUS_RING_WIDTH / 2 if focused else 0.5  # keeps the thick ring inside the widget
        shape = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        painter.setBrush(background)
        painter.setPen(focus_pen(palette) if focused else border)
        painter.drawRoundedRect(shape, appearance.BUTTON_RADIUS, appearance.BUTTON_RADIUS)

        side = appearance.ACTION_ICON_SIZE
        left = (self.width() - side) / 2 if self._compact else appearance.ACTION_BUTTON_PADDING
        paint_icon(painter, self._icon, QRectF(left, (self.height() - side) / 2, side, side), ink)
        if self._compact:
            return
        text_left = left + side + appearance.ACTION_ICON_GAP
        painter.setPen(ink)
        painter.drawText(
            QRectF(text_left, 0, self.width() - text_left, self.height()),
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
            self.text(),
        )
