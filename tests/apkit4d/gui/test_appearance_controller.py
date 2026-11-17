"""
Unit tests for AppearanceController.
"""

from unittest.mock import MagicMock

import pytest
from matplotlib import colormaps
from PySide6.QtWidgets import QComboBox, QPushButton

from apkit4d.gui.constants import names, view_style
from apkit4d.gui.controllers.appearance_controller import AppearanceController, readable_color
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.frame_slider import FrameSlider


@pytest.fixture
def panel(qtbot) -> LeftPanel:
    left_panel = LeftPanel()
    qtbot.addWidget(left_panel)
    return left_panel


@pytest.fixture
def view() -> MagicMock:
    # stands for the 3D view, it records the calls of the controller
    return MagicMock()


@pytest.fixture
def controller(panel, view) -> AppearanceController:
    return AppearanceController(panel, view, Theme.DARK)


def button_color(panel, name) -> str:
    return panel.findChild(ColorButton, name).color


def test_every_colormap_offered_exists_in_matplotlib() -> None:
    assert all(name in colormaps for name in view_style.COLORMAPS)


def test_view_starts_with_the_choices_of_the_panel(controller, view) -> None:
    view.set_colormap.assert_called_with(view_style.COLORMAPS[0])
    view.set_volume_opacity.assert_called_with(1.0)


def test_colors_start_with_the_theme(controller, view, panel) -> None:
    view.set_background.assert_called_with(DARK_COLORS.base)
    view.set_outline_color.assert_called_with(DARK_COLORS.text)
    view.set_text_color.assert_called_with(DARK_COLORS.text)
    assert button_color(panel, names.BACKGROUND_BUTTON) == DARK_COLORS.base
    assert button_color(panel, names.OUTLINE_BUTTON) == DARK_COLORS.text


def test_colors_follow_the_theme_until_the_user_chooses(controller, view, panel) -> None:
    controller.set_theme(Theme.LIGHT)

    view.set_background.assert_called_with(LIGHT_COLORS.base)
    view.set_outline_color.assert_called_with(LIGHT_COLORS.text)
    view.set_text_color.assert_called_with(LIGHT_COLORS.text)
    assert button_color(panel, names.BACKGROUND_BUTTON) == LIGHT_COLORS.base


def test_controls_of_the_panel_reach_the_view(controller, view, panel) -> None:
    panel.findChild(QComboBox, names.COLORMAP_COMBO).setCurrentText("viridis")
    view.set_colormap.assert_called_with("viridis")

    panel.findChild(FrameSlider, names.OPACITY_SLIDER).setValue(250)
    view.set_volume_opacity.assert_called_with(2.5)


def test_chosen_background_stays_with_the_theme_and_the_text_follows_it(controller, view, panel) -> None:
    panel.background_chosen.emit("#ffffff")

    view.set_background.assert_called_with("#ffffff")
    view.set_text_color.assert_called_with(LIGHT_COLORS.text)  # dark text on a white background
    view.set_outline_color.assert_called_with(LIGHT_COLORS.text)
    assert button_color(panel, names.BACKGROUND_BUTTON) == "#ffffff"

    controller.set_theme(Theme.LIGHT)
    controller.set_theme(Theme.DARK)
    view.set_background.assert_called_with("#ffffff")


def test_chosen_outline_stays_when_the_background_changes(controller, view, panel) -> None:
    panel.outline_chosen.emit("#ff0000")
    controller.set_theme(Theme.LIGHT)

    view.set_outline_color.assert_called_with("#ff0000")
    assert button_color(panel, names.OUTLINE_BUTTON) == "#ff0000"


@pytest.mark.parametrize(
    ("background", "expected"),
    [
        ("#000000", DARK_COLORS.text),
        ("#ffffff", LIGHT_COLORS.text),
        ("#0000ff", DARK_COLORS.text),  # pure blue looks dark
        ("#ffff00", LIGHT_COLORS.text),  # yellow looks light
        ("#00ff00", LIGHT_COLORS.text),  # bright green looks light
        (DARK_COLORS.base, DARK_COLORS.text),
        (LIGHT_COLORS.base, LIGHT_COLORS.text),
    ],
)
def test_readable_color_is_light_on_dark_backgrounds_and_dark_on_light_ones(background, expected) -> None:
    assert readable_color(background) == expected


def test_main_controller_connects_the_3d_view_to_the_left_panel_and_the_theme(qtbot, qapp, view) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window, view=view)
    assert controller.appearance_controller is not None
    view.set_background.assert_called_with(DARK_COLORS.base)

    window.findChild(QPushButton, names.THEME_BUTTON).click()
    view.set_background.assert_called_with(LIGHT_COLORS.base)


def test_main_controller_has_no_appearance_controller_without_a_3d_view(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    assert MainController(window, qapp, window).appearance_controller is None
