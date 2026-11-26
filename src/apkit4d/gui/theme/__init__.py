"""
Look of the application: the colors of the themes, the Qt palette and the stylesheet.

    themes      the `Theme` enum, `ThemeColors`, `StatusColors`, and color palettes
    tokens      sizes, fonts and color mixes shared by every component (design tokens)
    colors      shades derived from the palette of the active theme with the mixes of `tokens`
    stylesheet  stylesheet of every control and component, with the tokens and the shades of `colors`
    apply       builds the Qt palette and the stylesheet of a theme and applies them to the application

This package centralizes how the application looks and is styled. Which theme is active is
decided by the `ThemeController`.
"""

from apkit4d.gui.theme.apply import apply_theme, build_palette
from apkit4d.gui.theme.themes import (
    DARK_COLORS,
    DARK_STATUS_COLORS,
    DEFAULT_THEME,
    LIGHT_COLORS,
    LIGHT_STATUS_COLORS,
    STATUS_THEME_COLORS,
    THEME_COLORS,
    StatusColors,
    Theme,
    ThemeColors,
)

__all__ = [
    "DARK_COLORS",
    "DARK_STATUS_COLORS",
    "DEFAULT_THEME",
    "LIGHT_COLORS",
    "LIGHT_STATUS_COLORS",
    "STATUS_THEME_COLORS",
    "THEME_COLORS",
    "StatusColors",
    "Theme",
    "ThemeColors",
    "apply_theme",
    "build_palette",
]
