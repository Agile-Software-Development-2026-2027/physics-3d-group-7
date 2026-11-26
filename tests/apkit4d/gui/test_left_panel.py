"""
Unit tests for LeftPanel.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QCheckBox, QColorDialog, QComboBox, QLabel, QPushButton, QSpinBox, QWidget

from apkit4d.gui.constants import appearance, names, texts, view_style
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.gui.views.widgets.accordion import AccordionSection
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.visualization.data_mapper import TrajectoryColorMode
from tests.apkit4d.gui.helper import painted_color


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
        (names.TRAJECTORY_COLOR_MODE_BOX, texts.BOX_TRAJECTORY_COLOR_MODE),
        (names.TRAJECTORY_COLORMAP_BOX, texts.BOX_TRAJECTORY_COLORMAP),
        (names.TRAJECTORY_TAIL_BOX, texts.BOX_TRAJECTORY_TAIL),
    ],
)
def test_appearance_section_has_a_box_for_each_setting(panel, name, title) -> None:
    box = panel.appearance_section.findChild(QWidget, name)
    assert box.findChild(QLabel).text() == title


def test_box_properties_give_the_boxes_of_the_section(panel) -> None:
    assert panel.appearance_section.findChild(QWidget, names.COLORMAP_BOX) is not None
    assert panel.appearance_section.findChild(QWidget, names.OPACITY_BOX) is not None
    assert panel.appearance_section.findChild(QWidget, names.BACKGROUND_BOX) is not None
    assert panel.appearance_section.findChild(QWidget, names.OUTLINE_BOX) is not None


def test_theme_button_asks_to_switch_the_theme(panel, qtbot) -> None:
    button = panel.findChild(QPushButton, names.THEME_BUTTON)
    with qtbot.waitSignal(panel.theme_switch_requested, timeout=1000):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_main_controller_keeps_the_left_panel_on_the_active_theme(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    MainController(window, qapp, window)
    window.show()
    header = window.left_panel.appearance_section.header_frame
    assert painted_color(header, header.width() - 3, header.height() // 2) == DARK_COLORS.button

    window.findChild(QPushButton, names.THEME_BUTTON).click()
    assert painted_color(header, header.width() - 3, header.height() // 2) == LIGHT_COLORS.button


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


def test_layers_and_appearance_hold_trajectory_controls_and_emit_signals(panel, qtbot) -> None:
    traj_cb = panel.layers_section.findChild(QCheckBox, names.SHOW_TRAJECTORIES_CHECKBOX)
    blobs_cb = panel.layers_section.findChild(QCheckBox, names.SHOW_BLOBS_CHECKBOX)
    tail_spin = panel.appearance_section.findChild(QSpinBox, names.TRAJECTORY_TAIL_SPINBOX)
    mode_combo = panel.appearance_section.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO)
    cmap_combo = panel.appearance_section.findChild(QComboBox, names.TRAJECTORY_COLORMAP_COMBO)

    assert panel.layers_section.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO) is None
    assert panel.layers_section.findChild(QComboBox, names.TRAJECTORY_COLORMAP_COMBO) is None
    assert traj_cb is not None and traj_cb.isHidden() and panel.show_trajectories is True
    assert blobs_cb is not None and blobs_cb.isHidden() and panel.show_blobs is True
    assert tail_spin is not None and tail_spin.specialValueText() == texts.TRAJECTORY_TAIL_ALL
    assert panel.trajectory_tail_length == view_style.TRAJECTORY_TAIL_DEFAULT
    assert mode_combo is not None and panel.trajectory_color_mode == TrajectoryColorMode.SPEED
    assert cmap_combo is not None and panel.trajectory_colormap == view_style.TRAJECTORY_COLORMAPS[0]
    assert cmap_combo.isEnabled()

    with qtbot.waitSignal(panel.trajectory_tail_changed, timeout=1000) as blocker:
        tail_spin.setValue(25)
    assert blocker.args == [25]

    with qtbot.waitSignal(panel.trajectory_color_mode_changed, timeout=1000) as blocker:
        mode_combo.setCurrentIndex(1)
    assert blocker.args == [TrajectoryColorMode.TRACK_ID]
    assert not cmap_combo.isEnabled()

    with qtbot.waitSignal(panel.show_trajectories_toggled, timeout=1000) as blocker:
        traj_cb.setChecked(False)
    assert blocker.args == [False]

    with qtbot.waitSignal(panel.show_blobs_toggled, timeout=1000) as blocker:
        blobs_cb.setChecked(False)
    assert blocker.args == [False]


def test_left_panel_includes_collapsed_vis_sub_roi_section(panel) -> None:
    section = panel.findChild(AccordionSection, names.VIS_SUB_ROI_SECTION)
    assert section is panel.vis_sub_roi_section
    assert section.title == texts.SECTION_VIS_SUB_ROI
    assert not section.is_expanded()
    assert section.outside_opacity == pytest.approx(0.01)
