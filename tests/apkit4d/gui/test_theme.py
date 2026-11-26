"""
Unit tests for theme palettes and status colors.
"""

from PySide6.QtGui import QPalette

from apkit4d.gui.theme import (
    DARK_COLORS,
    DARK_STATUS_COLORS,
    DEFAULT_THEME,
    LIGHT_COLORS,
    LIGHT_STATUS_COLORS,
    STATUS_THEME_COLORS,
    THEME_COLORS,
    Theme,
    apply_theme,
    build_palette,
)


def test_theme_enum_and_defaults() -> None:
    assert Theme.LIGHT.opposite == Theme.DARK
    assert Theme.DARK.opposite == Theme.LIGHT
    assert DEFAULT_THEME == Theme.DARK
    assert THEME_COLORS[Theme.LIGHT] == LIGHT_COLORS
    assert THEME_COLORS[Theme.DARK] == DARK_COLORS
    assert STATUS_THEME_COLORS[Theme.LIGHT] == LIGHT_STATUS_COLORS
    assert STATUS_THEME_COLORS[Theme.DARK] == DARK_STATUS_COLORS


def test_build_palette() -> None:
    palette = build_palette(DARK_COLORS)
    assert isinstance(palette, QPalette)
    assert palette.color(QPalette.ColorRole.Window).name().lower() == DARK_COLORS.window.lower()
    assert (
        palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText).name().lower()
        == DARK_COLORS.disabled_text.lower()
    )


def test_apply_theme_to_application(qapp) -> None:
    apply_theme(qapp, Theme.LIGHT)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == LIGHT_COLORS.window.lower()

    apply_theme(qapp, Theme.DARK)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == DARK_COLORS.window.lower()
