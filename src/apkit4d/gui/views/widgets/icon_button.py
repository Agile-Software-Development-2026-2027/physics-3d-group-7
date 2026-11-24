"""
Round or rounded-square button that shows an icon, painted with the colors of the theme.
"""

from typing import override

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent
from PySide6.QtWidgets import QPushButton, QWidget

from apkit4d.gui.theme import tokens
from apkit4d.gui.theme.colors import focus_pen, plain_button_colors, primary_button_colors
from apkit4d.gui.views.widgets.icons import Icon, paint_icon


class IconButton(QPushButton):
    """
    Button that shows an icon instead of a text.

    The text of the button is not drawn, but it stays available, for the tools that read the interface
    aloud and for the tests. The primary button is a filled circle in the accent color and is meant for
    the main action, which is play.

    Args:
        icon: The icon to show.
        size: Width and height of the button.
        icon_size: Width and height of the icon.
        primary: True for the button of the main action.
        flat: True for a button without background and border, until the mouse is over it.
        parent: Qt parent.
    """

    def __init__(
        self,
        icon: Icon,
        size: int,
        icon_size: int,
        *,
        primary: bool = False,
        flat: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._icon_size = icon_size
        self._primary = primary
        self._flat = flat
        self.setFixedSize(size, size)
        self.setFocusPolicy(Qt.FocusPolicy.TabFocus)  # the focus ring is for the keyboard, not for the mouse

    @property
    def icon_kind(self) -> Icon:
        """The icon that the button shows."""
        return self._icon

    def set_icon_kind(self, icon: Icon) -> None:
        """
        Change the icon that the button shows.

        Args:
            icon: The new icon.
        """
        self._icon = icon
        self.update()

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        if self.width() <= 0 or self.height() <= 0:
            return
        painter = QPainter(self)
        if not painter.isActive():
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background, border, icon_color = self._colors()
        focused = self.hasFocus()
        inset = tokens.FOCUS_RING_WIDTH / 2 if focused else 0.5  # keeps the thick ring inside the widget
        shape = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        radius = shape.width() / 2 if self._primary else tokens.BUTTON_RADIUS
        painter.setBrush(background)
        painter.setPen(focus_pen(self.palette(), primary=self._primary) if focused else border)
        painter.drawRoundedRect(shape, radius, radius)

        side = self._icon_size
        icon_area = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        paint_icon(painter, self._icon, icon_area, icon_color)

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        """Background, border and icon colors for the state of the button."""
        enabled, down, hovered = self.isEnabled(), self.isDown(), self.underMouse()
        if self._primary:
            return primary_button_colors(self.palette(), enabled=enabled, down=down, hovered=hovered)
        return plain_button_colors(
            self.palette(), enabled=enabled, down=down, hovered=hovered, flat=self._flat
        )
