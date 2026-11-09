import pytest
from PySide6.QtCore import QObject
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
)

from apkit4d.gui.constants import names
from apkit4d.gui.models.output_type import OutputType
from apkit4d.gui.views.widgets.blob_detection_inspector import BlobDetectionInspector
from tests.apkit4d.gui.helper import find_widget


@pytest.fixture
def inspector(qtbot) -> BlobDetectionInspector:
    widget = BlobDetectionInspector()
    qtbot.addWidget(widget)
    return widget


def test_widgets_have_unique_object_names(inspector):
    object_names = [
        names.DETECTION_INSPECTOR_BATCH_PROCESSING_GROUP,
        names.DETECTION_INSPECTOR_DETECTION_PARAMETERS_GROUP,
        names.DETECTION_INSPECTOR_FRAME_START,
        names.DETECTION_INSPECTOR_FRAME_END,
        names.DETECTION_INSPECTOR_OUTPUT_FOLDER,
        names.DETECTION_INSPECTOR_OUTPUT_BROWSE_BUTTON,
        names.DETECTION_INSPECTOR_WORKERS,
        names.DETECTION_INSPECTOR_OUTPUT_FORMAT,
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
    ]

    assert len(object_names) == len(set(object_names))
    for object_name in object_names:
        assert len(inspector.findChildren(QObject, object_name)) == 1


def test_output_format_options(inspector):
    output_format = find_widget(inspector, QComboBox, names.DETECTION_INSPECTOR_OUTPUT_FORMAT)

    assert output_format.count() == len(OutputType)

    for index, output_type in enumerate(OutputType):
        assert output_format.itemData(index) == output_type


def test_frame_start_cannot_exceed_frame_end(inspector):
    frame_start = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_FRAME_START)
    frame_end = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_FRAME_END)

    frame_end.setValue(10)
    frame_start.setValue(20)

    assert frame_start.value() == 20
    assert frame_end.value() == 20


def test_frame_start_changed_signal_is_emitted(qtbot, inspector):
    frame_start = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_FRAME_START)

    with qtbot.waitSignal(inspector.frame_start_changed) as blocker:
        frame_start.setValue(10)

    assert blocker.args == [10]


def test_frame_end_cannot_be_lower_than_frame_start(inspector):
    frame_start = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_FRAME_START)
    frame_end = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_FRAME_END)

    frame_start.setValue(10)
    frame_end.setValue(5)

    assert frame_start.value() == 5
    assert frame_end.value() == 5


def test_frame_end_changed_signal_is_emitted(qtbot, inspector):
    frame_end = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_FRAME_END)

    with qtbot.waitSignal(inspector.frame_end_changed) as blocker:
        frame_end.setValue(10)

    assert blocker.args == [10]


def test_output_folder_changed_signal_is_emitted(qtbot, inspector, tmp_path):
    output_folder = find_widget(inspector, QLineEdit, names.DETECTION_INSPECTOR_OUTPUT_FOLDER)

    with qtbot.waitSignal(inspector.output_folder_changed) as blocker:
        output_folder.setText(str(tmp_path))

    assert blocker.args == [tmp_path]


def test_browse_output_folder(monkeypatch, inspector, tmp_path):
    output_folder = find_widget(inspector, QLineEdit, names.DETECTION_INSPECTOR_OUTPUT_FOLDER)
    browse_button = find_widget(inspector, QPushButton, names.DETECTION_INSPECTOR_OUTPUT_BROWSE_BUTTON)

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args: str(tmp_path),
    )

    browse_button.click()

    assert output_folder.text() == str(tmp_path)


def test_detection_status_is_updated(inspector):
    detection_status = find_widget(inspector, QLabel, names.DETECTION_INSPECTOR_DETECTION_STATUS)
    status = "Detection completed"

    inspector.set_detection_status(status)

    assert detection_status.text() == status


def test_find_blobs_clicked_signal_is_emitted(qtbot, inspector):
    find_blobs_button = find_widget(inspector, QPushButton, names.DETECTION_INSPECTOR_FIND_BLOBS_BUTTON)

    with qtbot.waitSignal(inspector.find_blob_clicked):
        find_blobs_button.click()


def test_output_format_changed_signal_is_emitted(qtbot, inspector):
    output_format = find_widget(inspector, QComboBox, names.DETECTION_INSPECTOR_OUTPUT_FORMAT)
    output_type = list(OutputType)[1]

    with qtbot.waitSignal(inspector.output_format_changed) as blocker:
        output_format.setCurrentIndex(1)

    assert blocker.args == [output_type]


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


def test_workers_changed_signal_is_emitted(qtbot, inspector):
    workers = find_widget(inspector, QSpinBox, names.DETECTION_INSPECTOR_WORKERS)

    with qtbot.waitSignal(inspector.workers_changed) as blocker:
        workers.setValue(5)

    assert blocker.args == [5]


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
