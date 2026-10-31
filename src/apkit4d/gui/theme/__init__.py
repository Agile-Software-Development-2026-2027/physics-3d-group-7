"""
Look of the application: the colors of the themes and the code that paints the application with them.

    themes  the `Theme` enum and the colors of each theme
    apply   builds the Qt palette of a theme and applies it to the application

This package only changes how the application looks. Which theme is active is decided by the
`ThemeController`.
"""

from apkit4d.gui.theme.apply import apply_theme, build_palette
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, Theme, ThemeColors

__all__ = ["DEFAULT_THEME", "THEME_COLORS", "Theme", "ThemeColors", "apply_theme", "build_palette"]
