import pytest
from PySide6.QtWidgets import QFileDialog

from apkit4d.gui.models.output_type import OutputType
from apkit4d.gui.views.widgets.blob_detection_inspector import BlobDetectionInspector


def test_output_format_options(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    assert inspector._output_format.count() == len(OutputType)

    for index, output_type in enumerate(OutputType):
        assert inspector._output_format.itemData(index) == output_type


def test_frame_start_cannot_exceed_frame_end(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    inspector._frame_end.setValue(10)
    inspector._frame_start.setValue(20)

    assert inspector._frame_start.value() == 20
    assert inspector._frame_end.value() == 20


def test_frame_start_changed_signal_is_emitted(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    with qtbot.waitSignal(inspector.frame_start_changed) as blocker:
        inspector._frame_start.setValue(10)

    assert blocker.args == [10]


def test_frame_end_cannot_be_lower_than_frame_start(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    inspector._frame_start.setValue(10)
    inspector._frame_end.setValue(5)

    assert inspector._frame_start.value() == 5
    assert inspector._frame_end.value() == 5


def test_frame_end_changed_signal_is_emitted(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    with qtbot.waitSignal(inspector.frame_end_changed) as blocker:
        inspector._frame_end.setValue(10)

    assert blocker.args == [10]


def test_output_folder_changed_signal_is_emitted(qtbot, tmp_path):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    with qtbot.waitSignal(inspector.output_folder_changed) as blocker:
        inspector._output_folder.setText(str(tmp_path))

    assert blocker.args == [tmp_path]


def test_browse_output_folder(qtbot, monkeypatch, tmp_path):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    monkeypatch.setattr(
        QFileDialog,
        "getExistingDirectory",
        lambda *args: str(tmp_path),
    )

    inspector.output_browse_button.click()

    assert inspector._output_folder.text() == str(tmp_path)


def test_detection_status_is_updated(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    status = "Detection completed"

    inspector.set_detection_status(status)

    assert inspector._detection_status.text() == status


def test_find_blobs_clicked_signal_is_emitted(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    with qtbot.waitSignal(inspector.find_blob_clicked):
        inspector._find_blobs_button.click()


def test_output_format_changed_signal_is_emitted(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    output_type = list(OutputType)[1]

    with qtbot.waitSignal(inspector.output_format_changed) as blocker:
        inspector._output_format.setCurrentIndex(1)

    assert blocker.args == [output_type]


@pytest.mark.parametrize(
    ("control_name", "signal_name"),
    [
        ("_diameter_z_equals_xy", "diameter_z_equal_to_xy_toggled"),
        ("_update_on_change", "update_on_change_toggled"),
        ("_show_segments", "show_segments_toggled"),
    ],
)
def test_checkbox_emits_signal(qtbot, control_name, signal_name):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    control = getattr(inspector, control_name)
    signal = getattr(inspector, signal_name)

    with qtbot.waitSignal(signal) as blocker:
        control.setChecked(True)

    assert blocker.args == [True]


def test_workers_changed_signal_is_emitted(qtbot):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    with qtbot.waitSignal(inspector.workers_changed) as blocker:
        inspector._workers.setValue(5)

    assert blocker.args == [5]


@pytest.mark.parametrize(
    ("control_name", "value"),
    [
        ("_workers", 8),
        ("_diameter_xy", 10.0),
        ("_diameter_z", 20.0),
        ("_lo_g_threshold", 0.5),
        ("_seed_separation", 0.5),
        ("_boundary", 0.5),
        ("_min_volume", 500.0),
        ("_max_volume", 1_000_100.0),
    ],
)
def test_numeric_control_emits_signal(qtbot, control_name, value):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    control = getattr(inspector, control_name)
    signal_name = {
        "_workers": "workers_changed",
        "_diameter_xy": "diameter_xy_changed",
        "_diameter_z": "diameter_z_changed",
        "_lo_g_threshold": "lo_g_changed",
        "_seed_separation": "seed_separation_changed",
        "_boundary": "boundary_changed",
        "_min_volume": "min_volume_changed",
        "_max_volume": "max_volume_changed",
    }[control_name]

    signal = getattr(inspector, signal_name)

    with qtbot.waitSignal(signal) as blocker:
        control.setValue(value)

    assert blocker.args == [value]
