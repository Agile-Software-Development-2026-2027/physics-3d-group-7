"""
Round or rounded-square button that shows an icon, painted with the colors of the theme.
"""

from typing import override

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QPushButton, QWidget

from apkit4d.gui.constants import appearance
from apkit4d.gui.views.widgets.colors import mix
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
        parent: Qt parent.
    """

    def __init__(
        self, icon: Icon, size: int, icon_size: int, *, primary: bool = False, parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._icon = icon
        self._icon_size = icon_size
        self._primary = primary
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
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        background, border, icon_color = self._colors()
        focused = self.hasFocus()
        inset = appearance.FOCUS_RING_WIDTH / 2 if focused else 0.5  # keeps the thick ring inside the widget
        shape = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        radius = shape.width() / 2 if self._primary else appearance.BUTTON_RADIUS
        painter.setBrush(background)
        painter.setPen(self._focus_pen() if focused else border)
        painter.drawRoundedRect(shape, radius, radius)

        side = self._icon_size
        icon_area = QRectF((self.width() - side) / 2, (self.height() - side) / 2, side, side)
        paint_icon(painter, self._icon, icon_area, icon_color)

    def _focus_pen(self) -> QPen:
        accent = self.palette().color(ColorRole.Highlight)
        color = mix(accent, QColor("white"), appearance.FOCUS_RING_LIGHTEN) if self._primary else accent
        return QPen(color, appearance.FOCUS_RING_WIDTH)

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        """Background, border and icon colors for the state of the button."""
        palette = self.palette()
        window = palette.color(ColorRole.Window)
        ink = palette.color(ColorRole.WindowText)
        disabled_ink = palette.color(ColorGroup.Disabled, ColorRole.ButtonText)
        none = QColor(0, 0, 0, 0)

        if self._primary:
            accent = palette.color(ColorRole.Highlight)
            if not self.isEnabled():
                return mix(window, ink, appearance.DISABLED_BORDER_MIX), none, disabled_ink
            if self.isDown():
                accent = accent.darker(appearance.ACCENT_PRESSED_DARKER)
            elif self.underMouse():
                accent = mix(accent, QColor("white"), appearance.ACCENT_HOVER_MIX)
            return accent, none, palette.color(ColorRole.HighlightedText)

        if not self.isEnabled():
            return none, mix(window, ink, appearance.DISABLED_BORDER_MIX), disabled_ink
        border = mix(window, ink, appearance.BORDER_MIX)
        background = palette.color(ColorRole.Button)
        if self.isDown():
            background = border
        elif self.underMouse():
            background = mix(background, ink, appearance.HOVER_MIX)
        return background, border, ink
