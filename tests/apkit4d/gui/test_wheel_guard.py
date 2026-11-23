"""Unit tests for WheelGuard across spinboxes, sliders, dropdowns, and scroll areas."""

import pytest
from PySide6.QtCore import QCoreApplication, QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QComboBox, QSpinBox

from apkit4d.gui.constants import names
from apkit4d.gui.models.pipeline_model import PipelineStep
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.stages.batch_inspector import BatchInspector
from tests.apkit4d.gui.helper import find_widget


def _send_wheel(
    target,
    *,
    delta_y: int = 120,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    center = QPointF(target.rect().center())
    global_pos = QPointF(target.mapToGlobal(target.rect().center()))
    event = QWheelEvent(
        center,
        global_pos,
        QPoint(0, 0),
        QPoint(0, delta_y),
        Qt.MouseButton.NoButton,
        modifiers,
        Qt.ScrollPhase.NoScrollPhase,
        False,
        Qt.MouseEventSource.MouseEventSynthesizedBySystem,
    )
    QCoreApplication.sendEvent(target, event)


@pytest.mark.parametrize(
    "modifiers",
    [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier],
)
def test_spinbox_wheel_only_changes_value_with_modifier_key(qtbot, modifiers) -> None:
    """Unmodified wheel over a right-panel spinbox scrolls the panel without changing the value."""
    panel = RightPanel()
    panel.resize(360, 260)
    panel.expand_all()
    panel.show()
    qtbot.addWidget(panel)
    qtbot.wait(50)

    inspector = panel.detection_inspector
    assert inspector is not None
    spin = inspector._diameter_xy
    initial = spin.value()

    bar = panel.scroll_area.verticalScrollBar()
    assert bar.maximum() > 0
    initial_scroll = bar.value()

    # Plain hover scroll: value stays unchanged, enclosing scroll area scrolls downward
    _send_wheel(spin, delta_y=-120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert spin.value() == initial
    assert bar.value() > initial_scroll

    scroll_after_hover = bar.value()
    # Modifier wheel (Ctrl or Shift): adjusts the spinbox value directly
    _send_wheel(spin, delta_y=120, modifiers=modifiers)
    expected_multiplier = 10 if modifiers == Qt.KeyboardModifier.ControlModifier else 1
    assert spin.value() == initial + spin.singleStep() * expected_multiplier
    assert bar.value() == scroll_after_hover


def test_slider_wheel_ignored_without_modifier_and_allowed_with_ctrl(qtbot) -> None:
    """Gamma slider in PreprocessingSection ignores hover wheel without Ctrl/Shift."""
    panel = RightPanel()
    qtbot.addWidget(panel)

    preproc = panel.get_section(PipelineStep.PREPROCESSING)
    assert preproc is not None
    slider = preproc.gamma_correction_to_apply
    initial = slider.value()

    _send_wheel(slider, delta_y=120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert slider.value() == initial

    _send_wheel(slider, delta_y=120, modifiers=Qt.KeyboardModifier.ControlModifier)
    assert slider.value() > initial


def test_tracking_spinbox_wheel_ignored_without_modifier(qtbot) -> None:
    """QSpinBox fields in Tracking inspector ignore unmodified wheel events."""
    panel = RightPanel()
    qtbot.addWidget(panel)
    min_len = find_widget(panel, QSpinBox, names.TRACKING_INSPECTOR_MIN_LEN)
    initial = min_len.value()

    _send_wheel(min_len, delta_y=120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert min_len.value() == initial


@pytest.mark.parametrize(
    "modifiers",
    [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier],
)
def test_right_panel_dropdown_wheel_only_changes_with_modifier_key(qtbot, modifiers) -> None:
    """Unmodified wheel over a right-panel dropdown scrolls the panel instead of changing selection."""
    panel = RightPanel()
    panel.resize(360, 260)
    panel.expand_all()
    panel.show()
    qtbot.addWidget(panel)
    qtbot.wait(50)

    combo = find_widget(panel, QComboBox, names.PREPROC_BG_MODE_COMBO)
    assert combo.isEnabled()
    combo.setCurrentIndex(1)
    initial = combo.currentIndex()

    bar = panel.scroll_area.verticalScrollBar()
    assert bar.maximum() > 0
    initial_scroll = bar.value()

    _send_wheel(combo, delta_y=-120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert combo.currentIndex() == initial
    assert bar.value() > initial_scroll

    scroll_after_hover = bar.value()
    _send_wheel(combo, delta_y=-120, modifiers=modifiers)
    assert combo.currentIndex() != initial
    assert bar.value() == scroll_after_hover


@pytest.mark.parametrize(
    "modifiers",
    [Qt.KeyboardModifier.ControlModifier, Qt.KeyboardModifier.ShiftModifier],
)
def test_left_panel_dropdown_wheel_only_changes_with_modifier_key(qtbot, modifiers) -> None:
    """Left-panel comboboxes forward unmodified wheels to scroll area and allow Ctrl/Shift edits."""
    panel = LeftPanel()
    panel.resize(260, 160)
    panel.layers_section.set_expanded(True, animate=False)
    panel.show()
    qtbot.addWidget(panel)
    qtbot.wait(50)

    combo = find_widget(panel, QComboBox, names.COLORMAP_COMBO)
    assert combo.isEnabled()
    combo.setCurrentIndex(1)
    initial = combo.currentIndex()

    bar = panel._scroll_area.verticalScrollBar()
    assert bar.maximum() > 0
    initial_scroll = bar.value()

    _send_wheel(combo, delta_y=-120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert combo.currentIndex() == initial
    assert bar.value() > initial_scroll

    scroll_after_hover = bar.value()
    _send_wheel(combo, delta_y=-120, modifiers=modifiers)
    assert combo.currentIndex() != initial
    assert bar.value() == scroll_after_hover


def test_batch_format_dropdown_wheel_ignored_without_modifier(qtbot) -> None:
    """Batch export format dropdown ignores unmodified hover wheel events when enabled."""
    panel = RightPanel()
    qtbot.addWidget(panel)
    batch = panel.findChild(BatchInspector)
    assert batch is not None
    batch.set_enabled_state(True)
    assert batch.format.isEnabled()
    initial = batch.format.currentIndex()

    _send_wheel(batch.format, delta_y=-120, modifiers=Qt.KeyboardModifier.NoModifier)
    assert batch.format.currentIndex() == initial

    _send_wheel(batch.format, delta_y=-120, modifiers=Qt.KeyboardModifier.ControlModifier)
    assert batch.format.currentIndex() != initial
