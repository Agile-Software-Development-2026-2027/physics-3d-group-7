"""
Unit tests for LeftPanel.
"""

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QComboBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QSpinBox,
)

from apkit4d.gui.constants import appearance, names, texts, view_style
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.appearance_section import AppearanceSection
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.gui.views.widgets.accordion import AccordionSection
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.visualization.data_mapper import TrajectoryColorMode


@pytest.fixture
def panel(qtbot) -> LeftPanel:
    left_panel = LeftPanel()
    qtbot.addWidget(left_panel)
    return left_panel


def test_left_panel_has_appearance_and_visualization_sections(panel) -> None:
    assert panel.objectName() == names.LEFT_PANEL
    assert panel.findChild(AccordionSection, names.APPEARANCE_SECTION) is panel.appearance_section
    assert panel.findChild(AccordionSection, names.VIS_SUB_ROI_SECTION) is panel.vis_sub_roi_section
    assert isinstance(panel.appearance_section, AppearanceSection)
    assert panel.appearance_section.title == texts.SECTION_APPEARANCE
    assert panel.vis_sub_roi_section.title == texts.SECTION_VIS_SUB_ROI


def test_only_the_appearance_section_starts_open(panel) -> None:
    assert panel.appearance_section.is_expanded()
    assert not panel.vis_sub_roi_section.is_expanded()


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
        (names.TRAJECTORY_COLOR_MODE_BOX, texts.BOX_TRAJECTORY_COLOR_MODE),
        (names.TRAJECTORY_COLORMAP_BOX, texts.BOX_TRAJECTORY_COLORMAP),
        (names.TRAJECTORY_TAIL_BOX, texts.BOX_TRAJECTORY_TAIL),
    ],
)
def test_appearance_section_has_a_form_label_for_each_setting(panel, name, title) -> None:
    label = panel.appearance_section.findChild(QLabel, name)
    assert label.text() == title


def test_appearance_section_uses_one_form_layout(panel) -> None:
    layouts = panel.appearance_section.findChildren(QFormLayout)
    assert len(layouts) == 1
    assert layouts[0].rowCount() == 8


def test_theme_button_asks_to_switch_the_theme(panel, qtbot) -> None:
    button = panel.findChild(QPushButton, names.THEME_BUTTON)
    with qtbot.waitSignal(panel.appearance_section.theme_switch_requested, timeout=1000):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_set_theme_paints_the_sections(panel) -> None:
    panel.set_theme(Theme.LIGHT)
    assert LIGHT_COLORS.button in panel.appearance_section.toggle_button.styleSheet()
    assert LIGHT_COLORS.button in panel.vis_sub_roi_section.toggle_button.styleSheet()

    panel.set_theme(Theme.DARK)
    assert DARK_COLORS.button in panel.appearance_section.toggle_button.styleSheet()
    assert DARK_COLORS.button in panel.vis_sub_roi_section.toggle_button.styleSheet()


def test_main_controller_keeps_the_left_panel_on_the_active_theme(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    MainController(window, qapp, window)
    toggle_button = window.left_panel._appearance_section.toggle_button
    assert DARK_COLORS.button in toggle_button.styleSheet()

    button = window.findChild(QPushButton, names.THEME_BUTTON)
    assert button is not None
    button.click()
    assert LIGHT_COLORS.button in toggle_button.styleSheet()


def test_each_box_holds_its_control(panel) -> None:
    assert panel.appearance_section.findChild(QComboBox, names.COLORMAP_COMBO) is not None
    assert panel.appearance_section.findChild(FrameSlider, names.OPACITY_SLIDER) is not None
    assert panel.appearance_section.findChild(ColorButton, names.BACKGROUND_BUTTON) is not None
    assert panel.appearance_section.findChild(ColorButton, names.OUTLINE_BUTTON) is not None
    assert panel.appearance_section.findChild(QSpinBox, names.TRAJECTORY_TAIL_SPINBOX) is not None
    assert panel.appearance_section.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO) is not None
    assert panel.appearance_section.findChild(QComboBox, names.TRAJECTORY_COLORMAP_COMBO) is not None


def test_colormap_combo_offers_the_colormaps_and_starts_on_the_first(panel) -> None:
    combo = panel.findChild(QComboBox, names.COLORMAP_COMBO)
    assert [combo.itemText(index) for index in range(combo.count())] == list(view_style.COLORMAPS)
    assert panel.appearance_section.colormap == view_style.COLORMAPS[0]


def test_choosing_a_colormap_emits_its_name(panel, qtbot) -> None:
    combo = panel.findChild(QComboBox, names.COLORMAP_COMBO)
    with qtbot.waitSignal(panel.appearance_section.colormap_chosen, timeout=1000) as blocker:
        combo.setCurrentIndex(1)
    assert blocker.args == [view_style.COLORMAPS[1]]
    assert panel.appearance_section.colormap == view_style.COLORMAPS[1]


def test_opacity_slider_starts_at_the_default_look(panel) -> None:
    slider = panel.findChild(FrameSlider, names.OPACITY_SLIDER)
    assert slider.minimum() == view_style.OPACITY_MIN_PERCENT
    assert slider.maximum() == view_style.OPACITY_MAX_PERCENT
    assert slider.value() == view_style.OPACITY_DEFAULT_PERCENT
    assert panel.appearance_section.volume_opacity == 1.0
    assert panel.findChild(QLabel, names.OPACITY_VALUE).text() == texts.OPACITY_VALUE.format(percent=100)


def test_moving_the_opacity_slider_emits_the_factor_and_shows_the_percent(panel, qtbot) -> None:
    slider = panel.findChild(FrameSlider, names.OPACITY_SLIDER)
    with qtbot.waitSignal(panel.appearance_section.opacity_changed, timeout=1000) as blocker:
        slider.setValue(250)
    assert blocker.args == [2.5]
    assert panel.appearance_section.volume_opacity == 2.5
    assert panel.findChild(QLabel, names.OPACITY_VALUE).text() == texts.OPACITY_VALUE.format(percent=250)


def test_opacity_slider_has_no_frame_preview(panel) -> None:
    slider = panel.findChild(FrameSlider, names.OPACITY_SLIDER)
    assert slider.height() == appearance.SLIDER_HEIGHT  # no room above the groove for the bubble


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
    with qtbot.waitSignal(getattr(panel.appearance_section, signal_name), timeout=1000) as blocker:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert blocker.args == ["#123456"]


def test_closing_the_color_dialog_emits_nothing(panel, qtbot, monkeypatch) -> None:
    # an invalid color is what the dialog returns when it is closed without choosing
    monkeypatch.setattr(QColorDialog, "getColor", lambda *args: QColor())
    button = panel.findChild(ColorButton, names.BACKGROUND_BUTTON)
    with qtbot.assertNotEmitted(panel.appearance_section.background_chosen):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_set_colors_shows_them_on_the_buttons(panel) -> None:
    panel.set_background_color("#1f2023")
    panel.set_outline_color("white")
    assert panel.findChild(ColorButton, names.BACKGROUND_BUTTON).color == "#1f2023"
    assert panel.findChild(ColorButton, names.OUTLINE_BUTTON).color == "#ffffff"


def test_layer_actions_emit_visibility_signals(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    window.set_current_file(Path("sample.czi"))

    volume_action = window.findChild(QAction, names.SHOW_VOLUME_ACTION)
    blobs_action = window.findChild(QAction, names.SHOW_BLOBS_ACTION)
    trajectories_action = window.findChild(QAction, names.SHOW_TRAJECTORIES_ACTION)

    assert volume_action is not None and volume_action.isChecked()
    assert blobs_action is not None and blobs_action.isChecked()
    assert trajectories_action is not None and trajectories_action.isChecked()

    with qtbot.waitSignal(window.show_volume_toggled, timeout=1000) as blocker:
        volume_action.setChecked(False)
    assert blocker.args == [False]

    with qtbot.waitSignal(window.left_panel.show_blobs_toggled, timeout=1000) as blocker:
        blobs_action.setChecked(False)
    assert blocker.args == [False]

    with qtbot.waitSignal(window.left_panel.show_trajectories_toggled, timeout=1000) as blocker:
        trajectories_action.setChecked(False)
    assert blocker.args == [False]


def test_appearance_section_holds_trajectory_controls(panel, qtbot) -> None:
    tail_spin = panel.appearance_section.findChild(QSpinBox, names.TRAJECTORY_TAIL_SPINBOX)
    mode_combo = panel.appearance_section.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO)
    cmap_combo = panel.appearance_section.findChild(QComboBox, names.TRAJECTORY_COLORMAP_COMBO)

    assert tail_spin is not None and tail_spin.specialValueText() == texts.TRAJECTORY_TAIL_ALL
    assert panel.appearance_section.trajectory_tail_length == view_style.TRAJECTORY_TAIL_DEFAULT
    assert mode_combo is not None
    assert panel.appearance_section.trajectory_color_mode == TrajectoryColorMode.SPEED
    assert cmap_combo is not None
    assert panel.appearance_section.trajectory_colormap == view_style.TRAJECTORY_COLORMAPS[0]
    assert cmap_combo.isEnabled()

    with qtbot.waitSignal(panel.appearance_section.trajectory_tail_changed, timeout=1000) as blocker:
        tail_spin.setValue(25)
    assert blocker.args == [25]

    with qtbot.waitSignal(panel.appearance_section.trajectory_color_mode_changed, timeout=1000) as blocker:
        mode_combo.setCurrentIndex(1)
    assert blocker.args == [TrajectoryColorMode.TRACK_ID]
    assert not cmap_combo.isEnabled()


def test_left_panel_includes_collapsed_vis_sub_roi_section(panel) -> None:
    section = panel.findChild(AccordionSection, names.VIS_SUB_ROI_SECTION)
    assert section is panel.vis_sub_roi_section
    assert section.title == texts.SECTION_VIS_SUB_ROI
    assert not section.is_expanded()
    assert section.outside_opacity == pytest.approx(0.01)


def test_set_theme_paints_vis_sub_roi_section(panel) -> None:
    panel.set_theme(Theme.LIGHT)
    assert LIGHT_COLORS.button in panel.vis_sub_roi_section.toggle_button.styleSheet()

    panel.set_theme(Theme.DARK)
    assert DARK_COLORS.button in panel.vis_sub_roi_section.toggle_button.styleSheet()
