"""
Unit tests for the stylesheet of the whole application.
"""

from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QPushButton

from apkit4d.gui.theme import tokens
from apkit4d.gui.theme.apply import apply_theme, build_palette
from apkit4d.gui.theme.colors import plain_button_colors
from apkit4d.gui.theme.stylesheet import build_stylesheet
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme, ThemeColors
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.icon_button import IconButton
from apkit4d.gui.views.widgets.icons import Icon

THEMES = pytest.mark.parametrize("colors", [LIGHT_COLORS, DARK_COLORS], ids=["light", "dark"])


def _css(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


@THEMES
def test_buttons_have_the_shades_of_the_playback_bar(colors: ThemeColors) -> None:
    palette = build_palette(colors)
    stylesheet = build_stylesheet(palette)
    for hovered, down in ((False, False), (True, False), (False, True)):
        background, _, _ = plain_button_colors(palette, enabled=True, down=down, hovered=hovered)
        assert _css(background) in stylesheet
    assert f"border-radius: {tokens.BUTTON_RADIUS}px" in stylesheet


@THEMES
def test_drop_down_arrow_is_an_image_of_the_text_color(colors: ThemeColors) -> None:
    stylesheet = build_stylesheet(build_palette(colors))
    arrow = Path(stylesheet.split(".QComboBox::down-arrow {")[1].split('url("')[1].split('")')[0])
    assert arrow.exists()
    assert colors.window_text in arrow.read_text(encoding="utf-8")


def test_apply_theme_sets_the_stylesheet(qapp) -> None:
    apply_theme(qapp, Theme.LIGHT)
    assert qapp.styleSheet() == build_stylesheet(build_palette(LIGHT_COLORS))
    apply_theme(qapp, Theme.DARK)
    assert qapp.styleSheet() == build_stylesheet(build_palette(DARK_COLORS))


def test_standard_controls_have_the_height_of_the_token(qapp, qtbot) -> None:
    apply_theme(qapp, Theme.DARK)
    button, color_button, combo = QPushButton("Accept"), ColorButton("Color"), QComboBox()
    for widget in (button, color_button, combo):
        qtbot.addWidget(widget)
        widget.show()
        assert widget.sizeHint().height() == tokens.CONTROL_HEIGHT


def test_flat_buttons_and_painted_buttons_are_left_alone(qapp, qtbot) -> None:
    apply_theme(qapp, Theme.DARK)
    flat = QPushButton("Toggle")
    flat.setFlat(True)
    flat.setStyleSheet("QPushButton { padding: 0px; }")  # a button with its own stylesheet, like a header
    painted = IconButton(Icon.PLAY, 44, 22)
    for widget in (flat, painted):
        qtbot.addWidget(widget)
        widget.show()
    assert flat.minimumHeight() == 0
    assert flat.sizeHint().height() < tokens.CONTROL_HEIGHT
    assert painted.size().height() == 44
