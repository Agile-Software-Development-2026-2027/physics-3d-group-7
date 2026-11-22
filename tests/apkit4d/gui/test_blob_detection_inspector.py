import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QLabel,
    QPushButton,
)

from apkit4d.core.models import DetectionConfig
from apkit4d.gui.constants import names, texts
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.stages import StageInspectorView
from apkit4d.gui.views.stages.blob_detection_inspector import BlobDetectionInspector
from tests.apkit4d.gui.helper import find_widget


@pytest.fixture
def inspector(qtbot) -> BlobDetectionInspector:
    widget = BlobDetectionInspector()
    qtbot.addWidget(widget)
    return widget


def test_widgets_have_unique_object_names(inspector):
    object_names = [
        names.DETECTION_INSPECTOR_DETECTION_PARAMETERS_GROUP,
        names.DETECTION_INSPECTOR_DIAMETER_XY,
        names.DETECTION_INSPECTOR_DIAMETER_Z,
        names.DETECTION_INSPECTOR_DIAMETER_Z_EQUALS_XY,
        names.DETECTION_INSPECTOR_LOG_THRESHOLD,
        names.DETECTION_INSPECTOR_SEED_SEPARATION,
        names.DETECTION_INSPECTOR_BOUNDARY,
        names.DETECTION_INSPECTOR_MIN_VOLUME,
        names.DETECTION_INSPECTOR_MAX_VOLUME,
        names.DETECTION_INSPECTOR_UPDATE_ON_CHANGE,
        names.DETECTION_INSPECTOR_SHOW_SEGMENTS,
        names.DETECTION_INSPECTOR_FIND_BLOBS_BUTTON,
        names.DETECTION_INSPECTOR_DETECTION_STATUS,
        names.DETECTION_INSPECTOR_RESET_BUTTON,
    ]

    assert len(object_names) == len(set(object_names))
    for object_name in object_names:
        assert len(inspector.findChildren(QObject, object_name)) == 1


def test_detection_status_is_updated(inspector):
    detection_status = find_widget(inspector, QLabel, names.DETECTION_INSPECTOR_DETECTION_STATUS)
    status = "Detection completed"

    inspector.set_detection_status(status)

    assert detection_status.text() == status


def test_find_blobs_clicked_signal_is_emitted(qtbot, inspector):
    find_blobs_button = find_widget(inspector, QPushButton, names.DETECTION_INSPECTOR_FIND_BLOBS_BUTTON)

    with qtbot.waitSignal(inspector.find_blob_clicked):
        find_blobs_button.click()


def test_reset_button_emits_signal(qtbot, inspector):
    reset_btn = find_widget(inspector, QPushButton, names.DETECTION_INSPECTOR_RESET_BUTTON)
    assert reset_btn.text() == texts.BUTTON_RESET_DEFAULTS

    with qtbot.waitSignal(inspector.reset_requested):
        reset_btn.click()


def test_normalization_warning_hidden_by_default_and_red_when_disabled(inspector):
    assert inspector._update_on_change_info.isHidden()
    assert inspector._find_blob_button_info.isHidden()
    assert DARK_COLORS.danger in inspector._update_on_change_info.styleSheet()
    assert DARK_COLORS.danger in inspector._find_blob_button_info.styleSheet()

    inspector.disable_update_on_change(True)
    inspector.disable_find_blob(True)
    assert not inspector._update_on_change_info.isHidden()
    assert not inspector._find_blob_button_info.isHidden()

    inspector.apply_theme(LIGHT_COLORS)
    assert LIGHT_COLORS.danger in inspector._update_on_change_info.styleSheet()
    assert LIGHT_COLORS.danger in inspector._find_blob_button_info.styleSheet()

    inspector.disable_update_on_change(False)
    inspector.disable_find_blob(False)
    assert inspector._update_on_change_info.isHidden()
    assert inspector._find_blob_button_info.isHidden()


@pytest.mark.parametrize(
    ("object_name", "signal_name"),
    [
        (names.DETECTION_INSPECTOR_DIAMETER_Z_EQUALS_XY, "diameter_z_equal_to_xy_toggled"),
        (names.DETECTION_INSPECTOR_UPDATE_ON_CHANGE, "update_on_change_toggled"),
        (names.DETECTION_INSPECTOR_SHOW_SEGMENTS, "show_segments_toggled"),
    ],
)
def test_checkbox_emits_signal(qtbot, inspector, object_name, signal_name):
    checkbox = find_widget(inspector, QCheckBox, object_name)
    signal = getattr(inspector, signal_name)

    with qtbot.waitSignal(signal) as blocker:
        checkbox.setChecked(True)

    assert blocker.args == [True]


@pytest.mark.parametrize(
    ("object_name", "signal_name", "value"),
    [
        (names.DETECTION_INSPECTOR_DIAMETER_XY, "diameter_xy_changed", 10.0),
        (names.DETECTION_INSPECTOR_DIAMETER_Z, "diameter_z_changed", 20.0),
        (names.DETECTION_INSPECTOR_LOG_THRESHOLD, "lo_g_changed", 0.5),
        (names.DETECTION_INSPECTOR_SEED_SEPARATION, "seed_separation_changed", 0.5),
        (names.DETECTION_INSPECTOR_BOUNDARY, "boundary_changed", 0.5),
        (names.DETECTION_INSPECTOR_MIN_VOLUME, "min_volume_changed", 500.0),
        (names.DETECTION_INSPECTOR_MAX_VOLUME, "max_volume_changed", 1_000_100.0),
    ],
)
def test_double_spinbox_emits_signal(qtbot, inspector, object_name, signal_name, value):
    spinbox = find_widget(inspector, QDoubleSpinBox, object_name)
    signal = getattr(inspector, signal_name)

    with qtbot.waitSignal(signal) as blocker:
        spinbox.setValue(value)

    assert blocker.args == [value]


def test_diameter_z_value_is_synched_with_diameter_xy_when_toggled(inspector):
    inspector._diameter_xy.setValue(8.0)
    inspector._diameter_z.setValue(30.0)

    diameter_z_equals_xy: QCheckBox = find_widget(
        inspector, QCheckBox, names.DETECTION_INSPECTOR_DIAMETER_Z_EQUALS_XY
    )
    diameter_z_equals_xy.setChecked(True)

    assert inspector._diameter_z_equals_xy.isChecked()
    assert inspector._diameter_z.value() == 8.0

    diameter_xy: QDoubleSpinBox = find_widget(
        inspector, QDoubleSpinBox, names.DETECTION_INSPECTOR_DIAMETER_XY
    )
    diameter_xy.setValue(10)
    assert inspector._diameter_z.value() == 10.0
    diameter_xy.stepDown()
    assert inspector._diameter_z.value() == 9.0


def test_diameter_z_is_disabled_while_equal_to_xy(inspector):
    diameter_z_equals_xy: QCheckBox = find_widget(
        inspector, QCheckBox, names.DETECTION_INSPECTOR_DIAMETER_Z_EQUALS_XY
    )
    diameter_z_equals_xy.setChecked(True)
    assert not inspector._diameter_z.isEnabled()


def test_blob_detection_inspector_set_params_blocks_signals_and_roundtrips(inspector):
    assert isinstance(inspector, StageInspectorView)

    emitted: list[tuple[str, object]] = []
    for sig_name in (
        "diameter_xy_changed",
        "diameter_z_changed",
        "diameter_z_equal_to_xy_toggled",
        "lo_g_changed",
        "seed_separation_changed",
        "boundary_changed",
        "min_volume_changed",
        "max_volume_changed",
    ):
        getattr(inspector, sig_name).connect(lambda v, name=sig_name: emitted.append((name, v)))

    inspector._diameter_z_equals_xy.setChecked(True)
    emitted.clear()

    custom = DetectionConfig(
        diameter_xy_um=12.0,
        diameter_z_um=48.0,
        threshold=0.35,
        split=1.5,
        grow_frac=0.45,
        min_volume_um3=350.0,
        max_volume_um3=50000.0,
    )
    inspector.set_params(custom)

    assert emitted == []
    assert inspector.get_params() == custom
    assert not inspector.z_equals_xy
    assert inspector._diameter_z.isEnabled()

    inspector.set_enabled_state(False)
    assert not inspector._diameter_xy.isEnabled()
    assert not inspector._find_blobs_button.isEnabled()
    assert not inspector._reset_button.isEnabled()

    inspector.set_enabled_state(True)
    assert inspector._diameter_xy.isEnabled()
    assert inspector._find_blobs_button.isEnabled()
    assert inspector._reset_button.isEnabled()
