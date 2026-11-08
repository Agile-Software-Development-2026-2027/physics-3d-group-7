"""
Look of the application: the colors of the themes, Qt palette builder, and QSS component stylers.

    themes  the `Theme` enum, `ThemeColors`, `StatusColors`, and color palettes
    apply   builds the Qt palette of a theme and applies it to the application
    style   QSS stylesheet generators and styler classes for all GUI components

This package centralizes how the application looks and is styled. Which theme is active is
decided by the `ThemeController`.
"""

from apkit4d.gui.theme.apply import apply_theme, build_palette
from apkit4d.gui.theme.style import (
    AccordionStyler,
    RightPanelStyler,
    ScrollAreaStyler,
    ThemeStyler,
    get_accordion_content_area_stylesheet,
    get_accordion_header_frame_stylesheet,
    get_accordion_play_button_stylesheet,
    get_accordion_toggle_button_stylesheet,
    get_bottom_stats_stylesheet,
    get_right_panel_top_bar_stylesheet,
    get_scroll_area_stylesheet,
    get_scrollbar_stylesheet,
    get_status_colors,
)
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
    "AccordionStyler",
    "RightPanelStyler",
    "ScrollAreaStyler",
    "StatusColors",
    "Theme",
    "ThemeColors",
    "ThemeStyler",
    "apply_theme",
    "build_palette",
    "get_accordion_content_area_stylesheet",
    "get_accordion_header_frame_stylesheet",
    "get_accordion_play_button_stylesheet",
    "get_accordion_toggle_button_stylesheet",
    "get_bottom_stats_stylesheet",
    "get_right_panel_top_bar_stylesheet",
    "get_scroll_area_stylesheet",
    "get_scrollbar_stylesheet",
    "get_status_colors",
]
