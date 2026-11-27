"""
Unit tests for the stylesheet of the whole application.
"""

from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QComboBox, QLabel, QProgressBar, QPushButton, QStyledItemDelegate

from apkit4d.gui.theme import tokens
from apkit4d.gui.theme.apply import apply_theme, build_palette
from apkit4d.gui.theme.colors import plain_button_colors
from apkit4d.gui.theme.stylesheet import build_stylesheet
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, THEME_COLORS, Theme
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.icon_button import IconButton
from apkit4d.gui.views.widgets.icons import Icon
from apkit4d.gui.views.widgets.scroll_area import ModernScrollArea

THEMES = pytest.mark.parametrize("theme", [Theme.LIGHT, Theme.DARK], ids=["light", "dark"])


def _css(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


@THEMES
def test_buttons_have_the_shades_of_the_playback_bar(theme: Theme) -> None:
    palette = build_palette(THEME_COLORS[theme])
    stylesheet = build_stylesheet(palette, theme)
    for hovered, down in ((False, False), (True, False), (False, True)):
        background, _, _ = plain_button_colors(palette, enabled=True, down=down, hovered=hovered)
        assert _css(background) in stylesheet
    assert f"border-radius: {tokens.BUTTON_RADIUS}px" in stylesheet


@THEMES
def test_drop_down_arrow_is_an_image_of_the_text_color(theme: Theme) -> None:
    colors = THEME_COLORS[theme]
    stylesheet = build_stylesheet(build_palette(colors), theme)
    arrow = Path(stylesheet.split(".QComboBox::down-arrow {")[1].split('url("')[1].split('")')[0])
    assert arrow.exists()
    assert colors.window_text in arrow.read_text(encoding="utf-8")


def test_apply_theme_sets_the_stylesheet(qapp) -> None:
    apply_theme(qapp, Theme.LIGHT)
    assert qapp.styleSheet() == build_stylesheet(build_palette(LIGHT_COLORS), Theme.LIGHT)
    apply_theme(qapp, Theme.DARK)
    assert qapp.styleSheet() == build_stylesheet(build_palette(DARK_COLORS), Theme.DARK)


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


def test_open_drop_down_list_shows_every_item(qapp, qtbot) -> None:
    apply_theme(qapp, Theme.DARK)
    combo = QComboBox()
    combo.addItems(["None", "Gaussian", "Percentile", "Rolling ball"])
    qtbot.addWidget(combo)
    combo.show()
    combo.showPopup()
    view = combo.view()
    last = view.visualRect(view.model().index(combo.count() - 1, 0))
    assert isinstance(combo.itemDelegate(), QStyledItemDelegate)  # it draws the items with the stylesheet
    assert last.bottom() <= view.viewport().height()  # the border of the list does not hide the last item
    combo.hidePopup()


def test_scroll_bars_are_slim(qapp, qtbot) -> None:
    apply_theme(qapp, Theme.DARK)
    scroll_area = ModernScrollArea()
    scroll_area.setWidget(QLabel("\n".join(["Row"] * 100)))
    qtbot.addWidget(scroll_area)
    scroll_area.resize(200, 100)
    scroll_area.show()
    assert scroll_area.verticalScrollBar().isVisible()
    assert scroll_area.verticalScrollBar().width() == tokens.SPACING


def test_busy_progress_bar_stays_inside_its_round_corners(qapp, qtbot) -> None:
    apply_theme(qapp, Theme.DARK)
    accent = DARK_COLORS.highlight
    bar = QProgressBar()
    bar.setRange(0, 0)  # busy: a bar moves from side to side and wraps around
    qtbot.addWidget(bar)
    bar.resize(300, tokens.CONTROL_HEIGHT)
    bar.show()
    for _ in range(40):  # the moving bar reaches both ends several times
        qtbot.wait(50)
        image = bar.grab().toImage()
        for x in (1, bar.width() - 2):  # outside the round corners of the track
            assert image.pixelColor(x, 1).name() != accent
