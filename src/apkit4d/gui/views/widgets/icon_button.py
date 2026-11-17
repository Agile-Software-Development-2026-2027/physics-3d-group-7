"""
Round or rounded-square button that shows an icon, painted with the colors of the theme.
"""

from typing import override

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QPushButton, QWidget

from apkit4d.gui.constants import appearance
from apkit4d.gui.views.widgets.colors import focus_pen, mix, plain_button_colors
from apkit4d.gui.views.widgets.icons import Icon, paint_icon

ColorRole = QPalette.ColorRole
ColorGroup = QPalette.ColorGroup


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
        inset = appearance.FOCUS_RING_WIDTH / 2 if focused else 0.5  # keeps the thick ring inside the widget
        shape = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        radius = shape.width() / 2 if self._primary else appearance.BUTTON_RADIUS
        painter.setBrush(background)
        painter.setPen(focus_pen(self.palette(), primary=self._primary) if focused else border)
        painter.drawRoundedRect(shape, radius, radius)

        side = self._icon_size
        icon_area = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        paint_icon(painter, self._icon, icon_area, icon_color)

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        """Background, border and icon colors for the state of the button."""
        palette = self.palette()
        if not self._primary:
            return plain_button_colors(
                palette,
                enabled=self.isEnabled(),
                down=self.isDown(),
                hovered=self.underMouse(),
                flat=self._flat,
            )
        window = palette.color(ColorRole.Window)
        ink = palette.color(ColorRole.WindowText)
        accent = palette.color(ColorRole.Highlight)
        none = QColor(0, 0, 0, 0)
        if not self.isEnabled():
            disabled_ink = palette.color(ColorGroup.Disabled, ColorRole.ButtonText)
            return mix(window, ink, appearance.DISABLED_BORDER_MIX), none, disabled_ink
        if self.isDown():
            accent = accent.darker(appearance.ACCENT_PRESSED_DARKER)
        elif self.underMouse():
            accent = mix(accent, QColor("white"), appearance.ACCENT_HOVER_MIX)
        return accent, none, palette.color(ColorRole.HighlightedText)
