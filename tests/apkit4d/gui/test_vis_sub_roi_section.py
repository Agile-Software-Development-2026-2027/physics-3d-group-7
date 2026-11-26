"""Unit tests for VisSubRoiSection."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QLabel, QPushButton

from apkit4d.gui.constants import appearance, names, texts, view_style
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.display.vis_sub_roi_section import VisSubRoiSection
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.visualization.vis_sub_roi import VisSubRoiState


@pytest.fixture
def section(qtbot) -> VisSubRoiSection:
    widget = VisSubRoiSection()
    qtbot.addWidget(widget)
    return widget


def test_defaults_and_initial_unavailable_state(section: VisSubRoiSection) -> None:
    assert section.objectName() == names.VIS_SUB_ROI_SECTION
    assert section.title == texts.SECTION_VIS_SUB_ROI
    assert not section.is_expanded()
    assert section.is_available is False
    assert section.is_sub_roi_enabled is False
    assert section.outside_opacity == pytest.approx(0.01)

    slider = section.findChild(FrameSlider, names.VIS_SUB_ROI_OPACITY_SLIDER)
    assert slider is not None
    assert slider.minimum() == view_style.VIS_SUB_ROI_OPACITY_MIN_PERCENT
    assert slider.maximum() == view_style.VIS_SUB_ROI_OPACITY_MAX_PERCENT
    assert slider.value() == view_style.VIS_SUB_ROI_OPACITY_DEFAULT_PERCENT
    assert slider.height() == appearance.SLIDER_HEIGHT
    assert not slider.isEnabled()

    value_label = section.findChild(QLabel, names.VIS_SUB_ROI_OPACITY_VALUE)
    assert value_label is not None
    assert value_label.text() == texts.OPACITY_VALUE.format(percent=1)

    status_label = section.findChild(QLabel, names.VIS_SUB_ROI_STATUS_LABEL)
    assert status_label is not None
    assert status_label.text() == texts.STATUS_VIS_SUB_ROI_UNAVAILABLE

    assert not section.findChild(QCheckBox, names.VIS_SUB_ROI_ENABLED_CHECKBOX).isEnabled()
    assert not section.findChild(QPushButton, names.VIS_SUB_ROI_SELECT_BUTTON).isEnabled()
    assert not section.findChild(QPushButton, names.VIS_SUB_ROI_RESET_BUTTON).isEnabled()
    assert section.toggle_button.isEnabled()


def test_availability_unlocks_and_locks_controls(section: VisSubRoiSection) -> None:
    section.set_available(True)
    assert section.is_available is True
    assert section.findChild(QCheckBox, names.VIS_SUB_ROI_ENABLED_CHECKBOX).isEnabled()
    assert section.findChild(QPushButton, names.VIS_SUB_ROI_SELECT_BUTTON).isEnabled()
    assert section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN).isEnabled()
    assert section.findChild(FrameSlider, names.VIS_SUB_ROI_OPACITY_SLIDER).isEnabled()
    assert section.findChild(QPushButton, names.VIS_SUB_ROI_RESET_BUTTON).isEnabled()
    assert (
        section.findChild(QLabel, names.VIS_SUB_ROI_STATUS_LABEL).text() == texts.STATUS_VIS_SUB_ROI_INACTIVE
    )

    section.set_available(False)
    assert section.is_available is False
    assert not section.findChild(QCheckBox, names.VIS_SUB_ROI_ENABLED_CHECKBOX).isEnabled()
    assert (
        section.findChild(QLabel, names.VIS_SUB_ROI_STATUS_LABEL).text()
        == texts.STATUS_VIS_SUB_ROI_UNAVAILABLE
    )


def test_user_interactions_emit_expected_signals(section: VisSubRoiSection, qtbot) -> None:
    section.set_available(True)
    section.set_volume_bounds((0.0, 50.0, 0.0, 40.0, 0.0, 30.0))

    checkbox = section.findChild(QCheckBox, names.VIS_SUB_ROI_ENABLED_CHECKBOX)
    with qtbot.waitSignal(section.enabled_toggled, timeout=1000) as blocker:
        checkbox.setChecked(True)
    assert blocker.args == [True]
    assert section.is_sub_roi_enabled is True

    select_btn = section.findChild(QPushButton, names.VIS_SUB_ROI_SELECT_BUTTON)
    with qtbot.waitSignal(section.select_region_clicked, timeout=1000):
        qtbot.mouseClick(select_btn, Qt.MouseButton.LeftButton)

    slider = section.findChild(FrameSlider, names.VIS_SUB_ROI_OPACITY_SLIDER)
    with qtbot.waitSignal(section.outside_opacity_changed, timeout=1000) as blocker:
        slider.setValue(25)
    assert blocker.args == [pytest.approx(0.25)]
    assert section.outside_opacity == pytest.approx(0.25)
    assert section.findChild(QLabel, names.VIS_SUB_ROI_OPACITY_VALUE).text() == "25%"

    x_min = section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN)
    with qtbot.waitSignal(section.bounds_edited, timeout=1000) as blocker:
        x_min.setValue(10.0)
    assert blocker.args == [(10.0, 50.0, 0.0, 40.0, 0.0, 30.0)]

    reset_btn = section.findChild(QPushButton, names.VIS_SUB_ROI_RESET_BUTTON)
    with qtbot.waitSignal(section.reset_clicked, timeout=1000):
        qtbot.mouseClick(reset_btn, Qt.MouseButton.LeftButton)


def test_inverted_spinbox_bounds_are_normalized(section: VisSubRoiSection, qtbot) -> None:
    section.set_available(True)
    section.set_volume_bounds((0.0, 50.0, 0.0, 50.0, 0.0, 50.0))
    section.set_sub_roi_bounds((10.0, 20.0, 10.0, 20.0, 10.0, 20.0))

    x_min = section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN)
    with qtbot.waitSignal(section.bounds_edited, timeout=1000) as blocker:
        x_min.setValue(35.0)
    assert blocker.args == [(20.0, 35.0, 10.0, 20.0, 10.0, 20.0)]
    assert section.bounds == pytest.approx((20.0, 35.0, 10.0, 20.0, 10.0, 20.0))


def test_programmatic_setters_do_not_emit_signals(section: VisSubRoiSection, qtbot) -> None:
    section.set_available(True)
    with (
        qtbot.assertNotEmitted(section.enabled_toggled),
        qtbot.assertNotEmitted(section.bounds_edited),
        qtbot.assertNotEmitted(section.outside_opacity_changed),
    ):
        section.set_volume_bounds((5.0, 25.0, 2.0, 18.0, 0.0, 12.0))
        section.set_state(
            VisSubRoiState(
                enabled=True,
                bounds=(8.0, 20.0, 4.0, 14.0, 2.0, 10.0),
                outside_opacity=0.15,
            )
        )

    assert section.is_sub_roi_enabled is True
    assert section.bounds == pytest.approx((8.0, 20.0, 4.0, 14.0, 2.0, 10.0))
    assert section.outside_opacity == pytest.approx(0.15)
    assert section.findChild(QLabel, names.VIS_SUB_ROI_OPACITY_VALUE).text() == "15%"


def test_apply_theme_updates_toggle_button_stylesheet(section: VisSubRoiSection) -> None:
    section.apply_theme(LIGHT_COLORS)
    assert LIGHT_COLORS.button in section.toggle_button.styleSheet()

    section.apply_theme(DARK_COLORS)
    assert DARK_COLORS.button in section.toggle_button.styleSheet()
