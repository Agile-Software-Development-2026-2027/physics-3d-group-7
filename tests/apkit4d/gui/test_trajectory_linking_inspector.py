
import pytest
from PySide6.QtWidgets import QDoubleSpinBox, QGroupBox, QSpinBox
from pytestqt.qtbot import QtBot

from apkit4d.gui.constants import names
from apkit4d.gui.views.widgets.trajectory_linking_inspector import (
    TrajectoryLinkingInspector,
)


@pytest.fixture
def inspector(qtbot: QtBot) -> TrajectoryLinkingInspector:
    widget = TrajectoryLinkingInspector()
    qtbot.addWidget(widget)
    return widget


def test_widgets_have_expected_object_names(
    inspector: TrajectoryLinkingInspector,
) -> None:
    assert (
        inspector.findChild(
            QGroupBox, names.TRACKING_INSPECTOR_PARAMETERS_GROUP
        )
        is not None
    )
    assert (
        inspector.findChild(QSpinBox, names.TRACKING_INSPECTOR_MIN_LEN)
        is not None
    )
    assert (
        inspector.findChild(QSpinBox, names.TRACKING_INSPECTOR_MAX_GAP)
        is not None
    )
    assert (
        inspector.findChild(QDoubleSpinBox, names.TRACKING_INSPECTOR_MAX_SPEED)
        is not None
    )


def test_default_values(inspector: TrajectoryLinkingInspector) -> None:
    assert inspector._min_len.value() == 5
    assert inspector._max_gap.value() == 3
    assert inspector._max_speed.value() == 250.0


def test_parameter_ranges(inspector: TrajectoryLinkingInspector) -> None:
    assert inspector._min_len.minimum() == 2
    assert inspector._min_len.maximum() == 1000

    assert inspector._max_gap.minimum() == 0
    assert inspector._max_gap.maximum() == 100

    assert inspector._max_speed.minimum() == 0.01
    assert inspector._max_speed.maximum() == 10000.0


def test_values_are_clamped(inspector: TrajectoryLinkingInspector) -> None:
    inspector._min_len.setValue(1)
    assert inspector._min_len.value() == 2

    inspector._max_gap.setValue(101)
    assert inspector._max_gap.value() == 100

    inspector._max_speed.setValue(-1.0)
    assert inspector._max_speed.value() == 0.01


def test_min_len_changed_signal(
    inspector: TrajectoryLinkingInspector, qtbot: QtBot
) -> None:
    with qtbot.waitSignal(inspector.min_len_changed) as blocker:
        inspector._min_len.setValue(6)

    assert blocker.args == [6]


def test_max_gap_changed_signal(
    inspector: TrajectoryLinkingInspector, qtbot: QtBot
) -> None:
    with qtbot.waitSignal(inspector.max_gap_changed) as blocker:
        inspector._max_gap.setValue(4)

    assert blocker.args == [4]


def test_max_speed_changed_signal(
    inspector: TrajectoryLinkingInspector, qtbot: QtBot
) -> None:
    with qtbot.waitSignal(inspector.max_speed_changed) as blocker:
        inspector._max_speed.setValue(300.0)

    assert blocker.args == [300.0]
