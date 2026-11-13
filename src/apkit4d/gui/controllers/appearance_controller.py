"""
Controller of the look of the 3D view: colormap, opacity, background and outline.

It connects the controls of the left panel to the 3D view. The background follows the theme until the
user chooses one, and the outline follows the background until the user chooses one, so that it stays
visible. The text of the scalar bar and of the axes always follows the background, to stay readable.
"""

from typing import Protocol

from PySide6.QtCore import QObject
from PySide6.QtGui import QColor

from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, THEME_COLORS, Theme
from apkit4d.gui.views.panels.left_panel import LeftPanel

# below this luminance (0 is black, 1 is white) a background counts as dark
DARK_BACKGROUND_LUMINANCE = 0.5

# how bright red, green and blue look to the eye: the weights of the ITU-R BT.601 standard for turning a
# color into gray. HSL lightness gives 0.5 to every pure color, so it would put dark text on pure blue
LUMA_WEIGHTS: tuple[float, float, float] = (0.299, 0.587, 0.114)


class AppearanceView(Protocol):
    """What the controller needs from the 3D view. `Viewport` provides it."""

    def set_colormap(self, name: str) -> None: ...

    def set_volume_opacity(self, opacity: float) -> None: ...

    def set_background(self, color: str) -> None: ...

    def set_outline_color(self, color: str) -> None: ...

    def set_text_color(self, color: str) -> None: ...


def readable_color(background: str) -> str:
    """
    Return a color for lines and text that can be read on `background`.

    It is the text color of the dark theme on dark backgrounds, and the one of the light theme on light
    backgrounds.

    Args:
        background: A color name or a hex code.
    """
    color = QColor(background)
    red, green, blue = LUMA_WEIGHTS
    luminance = red * color.redF() + green * color.greenF() + blue * color.blueF()
    return DARK_COLORS.text if luminance < DARK_BACKGROUND_LUMINANCE else LIGHT_COLORS.text


class AppearanceController(QObject):
    """
    Applies the choices of the left panel to the 3D view, and keeps the colors of the view readable.

    When it is created, it gives the 3D view the choices that the panel starts with and the colors of
    `theme`.

    Args:
        panel: The left panel, with the controls.
        view: The 3D view.
        theme: The active theme.
        parent: Qt parent, so the controller lives as long as its owner.
    """

    def __init__(
        self, panel: LeftPanel, view: AppearanceView, theme: Theme, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._panel = panel
        self._view = view
        self._theme = theme
        self._background: str | None = None  # chosen by the user, None while it follows the theme
        self._outline: str | None = None  # chosen by the user, None while it follows the background

        panel.colormap_chosen.connect(view.set_colormap)
        panel.opacity_changed.connect(view.set_volume_opacity)
        panel.background_chosen.connect(self.set_background)
        panel.outline_chosen.connect(self.set_outline_color)

        view.set_colormap(panel.colormap)
        view.set_volume_opacity(panel.volume_opacity)
        self._apply_colors()

    def set_theme(self, theme: Theme) -> None:
        """
        Follow `theme`: the background changes with it, unless the user chose one.

        Args:
            theme: The new active theme.
        """
        self._theme = theme
        self._apply_colors()

    def set_background(self, color: str) -> None:
        """
        Use `color` as background from now on, whatever the theme.

        Args:
            color: A color name or a hex code.
        """
        self._background = color
        self._apply_colors()

    def set_outline_color(self, color: str) -> None:
        """
        Use `color` for the outline from now on, whatever the background.

        Args:
            color: A color name or a hex code.
        """
        self._outline = color
        self._apply_colors()

    def _apply_colors(self) -> None:
        background = self._background if self._background is not None else THEME_COLORS[self._theme].base
        readable = readable_color(background)
        outline = self._outline if self._outline is not None else readable

        self._view.set_background(background)
        self._view.set_outline_color(outline)
        self._view.set_text_color(readable)
        self._panel.set_background_color(background)
        self._panel.set_outline_color(outline)
