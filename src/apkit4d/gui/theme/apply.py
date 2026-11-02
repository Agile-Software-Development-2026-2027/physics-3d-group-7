"""
Paints the application with a theme.
"""

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from apkit4d.gui.constants import application
from apkit4d.gui.theme.themes import THEME_COLORS, Theme, ThemeColors

ColorRole = QPalette.ColorRole
ColorGroup = QPalette.ColorGroup


def build_palette(colors: ThemeColors) -> QPalette:
    """
    Build the Qt palette that paints the widgets with `colors`.

    Args:
        colors: Colors of the theme.

    Returns:
        The palette. Widgets that are disabled use a dimmed text color.
    """
    palette = QPalette(QColor(colors.button))  # the shades of the borders are derived from the button
    assignments = {
        ColorRole.Window: colors.window,
        ColorRole.WindowText: colors.window_text,
        ColorRole.Base: colors.base,
        ColorRole.AlternateBase: colors.alternate_base,
        ColorRole.Text: colors.text,
        ColorRole.PlaceholderText: colors.placeholder_text,
        ColorRole.Button: colors.button,
        ColorRole.ButtonText: colors.button_text,
        ColorRole.Highlight: colors.highlight,
        ColorRole.HighlightedText: colors.highlighted_text,
        ColorRole.Link: colors.link,
        ColorRole.ToolTipBase: colors.tool_tip_base,
        ColorRole.ToolTipText: colors.tool_tip_text,
    }
    for role, color in assignments.items():
        palette.setColor(role, QColor(color))

    disabled = QColor(colors.disabled_text)
    for role in (ColorRole.WindowText, ColorRole.Text, ColorRole.ButtonText):
        palette.setColor(ColorGroup.Disabled, role, disabled)
    return palette


def apply_theme(app: QApplication, theme: Theme) -> None:
    """
    Paint the whole application with `theme`.

    Args:
        app: The application to paint.
        theme: Theme to apply.
    """
    app.setStyle(application.QT_STYLE)  # changing the style resets the palette, so it comes first
    app.setPalette(build_palette(THEME_COLORS[theme]))
