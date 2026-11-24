"""Tests of the shades derived from the palette of a theme."""

import pytest
from PySide6.QtGui import QColor, QPalette

from apkit4d.gui.theme import tokens
from apkit4d.gui.theme.apply import build_palette
from apkit4d.gui.theme.colors import (
    TRANSPARENT,
    focus_pen,
    mix,
    plain_button_colors,
    primary_button_colors,
)
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, ThemeColors

ColorRole = QPalette.ColorRole


@pytest.fixture(params=[LIGHT_COLORS, DARK_COLORS], ids=["light", "dark"])
def colors(request: pytest.FixtureRequest) -> ThemeColors:
    return request.param


def test_mix_returns_the_ends_and_the_middle() -> None:
    black, white = QColor("black"), QColor("white")
    assert mix(black, white, 0) == black
    assert mix(black, white, 1) == white
    assert mix(black, white, 0.5) == QColor(128, 128, 128)


def test_plain_button_has_the_button_color_and_a_border_mixed_from_window_and_text(colors) -> None:
    palette = build_palette(colors)
    background, border, ink = plain_button_colors(palette, enabled=True, down=False, hovered=False)
    assert background == QColor(colors.button)
    assert border == mix(QColor(colors.window), QColor(colors.window_text), tokens.BORDER_MIX)
    assert ink == QColor(colors.window_text)


def test_plain_button_changes_while_hovered_and_pressed(colors) -> None:
    palette = build_palette(colors)
    idle, border, _ = plain_button_colors(palette, enabled=True, down=False, hovered=False)
    hovered, _, _ = plain_button_colors(palette, enabled=True, down=False, hovered=True)
    pressed, _, _ = plain_button_colors(palette, enabled=True, down=True, hovered=True)
    assert hovered == mix(QColor(colors.button), QColor(colors.window_text), tokens.HOVER_MIX)
    assert pressed == border
    assert len({idle.name(), hovered.name(), pressed.name()}) == 3


def test_flat_button_has_no_background_and_no_border_until_hovered(colors) -> None:
    palette = build_palette(colors)
    background, border, _ = plain_button_colors(palette, enabled=True, down=False, hovered=False, flat=True)
    assert background == TRANSPARENT
    assert border == TRANSPARENT


def test_disabled_plain_button_uses_the_disabled_text(colors) -> None:
    palette = build_palette(colors)
    background, _, ink = plain_button_colors(palette, enabled=False, down=False, hovered=False)
    assert background == TRANSPARENT
    assert ink == QColor(colors.disabled_text)


def test_primary_button_is_filled_with_the_accent_color(colors) -> None:
    palette = build_palette(colors)
    background, border, ink = primary_button_colors(palette, enabled=True, down=False, hovered=False)
    assert background == QColor(colors.highlight)
    assert border == TRANSPARENT
    assert ink == QColor(colors.highlighted_text)


def test_primary_button_is_lighter_while_hovered_and_darker_while_pressed(colors) -> None:
    palette = build_palette(colors)
    accent = QColor(colors.highlight)
    hovered, _, _ = primary_button_colors(palette, enabled=True, down=False, hovered=True)
    pressed, _, _ = primary_button_colors(palette, enabled=True, down=True, hovered=True)
    assert hovered == mix(accent, QColor("white"), tokens.ACCENT_HOVER_MIX)
    assert pressed == accent.darker(tokens.ACCENT_PRESSED_DARKER)


def test_disabled_primary_button_loses_the_accent_color(colors) -> None:
    palette = build_palette(colors)
    background, _, ink = primary_button_colors(palette, enabled=False, down=False, hovered=False)
    assert background != QColor(colors.highlight)
    assert ink == QColor(colors.disabled_text)


def test_focus_ring_is_the_accent_color_and_lighter_on_a_primary_button(colors) -> None:
    palette = build_palette(colors)
    accent = palette.color(ColorRole.Highlight)
    assert focus_pen(palette).color() == accent
    assert focus_pen(palette).width() == tokens.FOCUS_RING_WIDTH
    assert focus_pen(palette, primary=True).color() == mix(accent, QColor("white"), tokens.FOCUS_RING_LIGHTEN)
