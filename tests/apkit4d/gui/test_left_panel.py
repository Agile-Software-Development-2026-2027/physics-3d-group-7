"""
Unit tests for LeftPanel.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog, QComboBox, QLabel, QPushButton, QWidget

from apkit4d.gui.constants import names, texts, view_style
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.shared.components.accordion import AccordionSection
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


def test_left_panel_has_the_two_sections(panel) -> None:
    assert panel.objectName() == names.LEFT_PANEL
    assert panel.findChild(AccordionSection, names.APPEARANCE_SECTION) is panel.appearance_section
    assert panel.findChild(AccordionSection, names.LAYERS_SECTION) is panel.layers_section
    assert panel.appearance_section.title == texts.SECTION_APPEARANCE
    assert panel.layers_section.title == texts.SECTION_LAYERS


def test_only_the_appearance_section_starts_open(panel) -> None:
    assert panel.appearance_section.is_expanded()
    assert not panel.layers_section.is_expanded()


def test_open_section_is_tall_enough_for_its_content(panel) -> None:
    content = panel.appearance_section.content_area
    assert content.maximumHeight() >= content.sizeHint().height()


@pytest.mark.parametrize(
    ("name", "title"),
    [
        (names.COLORMAP_BOX, texts.BOX_COLORMAP),
        (names.OPACITY_BOX, texts.BOX_OPACITY),
        (names.BACKGROUND_BOX, texts.BOX_BACKGROUND),
        (names.OUTLINE_BOX, texts.BOX_OUTLINE),
    ],
)
def test_appearance_section_has_a_box_for_each_setting(panel, name, title) -> None:
    box = panel.appearance_section.findChild(QWidget, name)
    assert box.findChild(QLabel).text() == title


def test_box_properties_give_the_boxes_of_the_section(panel) -> None:
    assert panel.colormap_box.objectName() == names.COLORMAP_BOX
    assert panel.opacity_box.objectName() == names.OPACITY_BOX
    assert panel.background_box.objectName() == names.BACKGROUND_BOX
    assert panel.outline_box.objectName() == names.OUTLINE_BOX


def test_theme_button_asks_to_switch_the_theme(panel, qtbot) -> None:
    button = panel.findChild(QPushButton, names.THEME_BUTTON)
    with qtbot.waitSignal(panel.theme_switch_requested, timeout=1000):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_set_theme_paints_the_sections(panel) -> None:
    panel.set_theme(Theme.LIGHT)
    assert LIGHT_COLORS.button in panel.appearance_section.toggle_button.styleSheet()
    assert LIGHT_COLORS.button in panel.layers_section.toggle_button.styleSheet()

    panel.set_theme(Theme.DARK)
    assert DARK_COLORS.button in panel.appearance_section.toggle_button.styleSheet()
    assert DARK_COLORS.button in panel.layers_section.toggle_button.styleSheet()


def test_main_controller_keeps_the_left_panel_on_the_active_theme(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    MainController(window, qapp, window)
    toggle_button = window.left_panel.appearance_section.toggle_button
    assert DARK_COLORS.button in toggle_button.styleSheet()

    window.findChild(QPushButton, names.THEME_BUTTON).click()
    assert LIGHT_COLORS.button in toggle_button.styleSheet()


def test_each_box_holds_its_control(panel) -> None:
    assert panel.colormap_box.findChild(QComboBox, names.COLORMAP_COMBO) is not None
    assert panel.opacity_box.findChild(FrameSlider, names.OPACITY_SLIDER) is not None
    assert panel.background_box.findChild(ColorButton, names.BACKGROUND_BUTTON) is not None
    assert panel.outline_box.findChild(ColorButton, names.OUTLINE_BUTTON) is not None


def test_colormap_combo_offers_the_colormaps_and_starts_on_the_first(panel) -> None:
    combo = panel.findChild(QComboBox, names.COLORMAP_COMBO)
    assert [combo.itemText(index) for index in range(combo.count())] == list(view_style.COLORMAPS)
    assert panel.colormap == view_style.COLORMAPS[0]


def test_choosing_a_colormap_emits_its_name(panel, qtbot) -> None:
    combo = panel.findChild(QComboBox, names.COLORMAP_COMBO)
    with qtbot.waitSignal(panel.colormap_chosen, timeout=1000) as blocker:
        combo.setCurrentIndex(1)
    assert blocker.args == [view_style.COLORMAPS[1]]
    assert panel.colormap == view_style.COLORMAPS[1]


def test_opacity_slider_starts_at_the_default_look(panel) -> None:
    slider = panel.findChild(FrameSlider, names.OPACITY_SLIDER)
    assert slider.minimum() == view_style.OPACITY_MIN_PERCENT
    assert slider.maximum() == view_style.OPACITY_MAX_PERCENT
    assert slider.value() == view_style.OPACITY_DEFAULT_PERCENT
    assert panel.volume_opacity == 1.0
    assert panel.findChild(QLabel, names.OPACITY_VALUE).text() == texts.OPACITY_VALUE.format(percent=100)


def test_moving_the_opacity_slider_emits_the_factor_and_shows_the_percent(panel, qtbot) -> None:
    slider = panel.findChild(FrameSlider, names.OPACITY_SLIDER)
    with qtbot.waitSignal(panel.opacity_changed, timeout=1000) as blocker:
        slider.setValue(250)
    assert blocker.args == [2.5]
    assert panel.volume_opacity == 2.5
    assert panel.findChild(QLabel, names.OPACITY_VALUE).text() == texts.OPACITY_VALUE.format(percent=250)


@pytest.mark.parametrize(
    ("button_name", "signal_name"),
    [(names.BACKGROUND_BUTTON, "background_chosen"), (names.OUTLINE_BUTTON, "outline_chosen")],
)
def test_color_buttons_emit_the_color_chosen_in_the_dialog(
    panel, qtbot, monkeypatch, button_name, signal_name
) -> None:
    # the user picks #123456 in the color dialog
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor("#123456"))
    button = panel.findChild(ColorButton, button_name)
    with qtbot.waitSignal(getattr(panel, signal_name), timeout=1000) as blocker:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["#123456"]


def test_closing_the_color_dialog_emits_nothing(panel, qtbot, monkeypatch) -> None:
    # an invalid color is what the dialog returns when it is closed without choosing
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor())
    button = panel.findChild(ColorButton, names.BACKGROUND_BUTTON)
    with qtbot.assertNotEmitted(panel.background_chosen):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_set_colors_shows_them_on_the_buttons(panel) -> None:
    panel.set_background_color("#1f2023")
    panel.set_outline_color("white")
    assert panel.findChild(ColorButton, names.BACKGROUND_BUTTON).color == "#1f2023"
    assert panel.findChild(ColorButton, names.OUTLINE_BUTTON).color == "#ffffff"
