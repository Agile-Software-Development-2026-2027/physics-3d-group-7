"""Saved results open on their recording and fill the pipeline as if the analysis had just run."""

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog

from apkit4d.batching.export import save_batch_results
from apkit4d.core.models import TrackingConfig
from apkit4d.gui.constants import names
from apkit4d.gui.controllers.file_controller import FileController
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.task_runner import wait_for_background_tasks
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziInfo
from apkit4d.io.session import PrecomputedSource


class FakeRecording:
    """Takes the place of the CziSource of the recording, without a real file to read."""

    def __init__(self, path, channel=0):
        self.path = path
        self.channel = channel
        self.info = CziInfo(str(path), 3, 2, 8, 8, 1, "uint16", 1.0, 1.0, 2.0, 0.5, "test")
        self.closed = False

    def read(self, t):
        return np.full((2, 8, 8), t, dtype=np.uint16)

    def close(self):
        self.closed = True


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    return win


@pytest.fixture
def saved(tmp_path):
    """Results of tmp_path/sample.czi with 4 blobs on 3 frames and one track."""
    recording = tmp_path / "sample.czi"
    recording.write_bytes(b"")
    detections = pd.DataFrame(
        {
            "frame": [0, 1, 1, 2],
            "x_um": [2.0, 3.0, 6.0, 4.0],
            "y_um": [2.0, 3.0, 6.0, 4.0],
            "z_um": [1.0, 1.0, 2.0, 1.0],
            "response": [0.5, 0.6, 0.7, 0.8],
        }
    )
    tracks = detections.iloc[[0, 1, 3]].assign(track_id=0)
    metadata = {
        "czi": str(recording),
        "channel": 0,
        "t0": 0,
        "t1": 2,
        "info": {"dt_s": 0.5},
        "preproc": {},
        "blob": {"threshold": 0.25},
    }
    result = save_batch_results(
        detections,
        metadata,
        tmp_path,
        "parquet",
        0,
        2,
        lambda *_: None,
        tracks=tracks,
        tracking_config=TrackingConfig(min_len=2),
    )
    return recording, result.params_path


def status(window):
    return window.statusBar().currentMessage()


def test_open_results_action_emits_the_chosen_json(window, qtbot, saved, monkeypatch):
    _, params = saved
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(params), ""))
    with qtbot.waitSignal(window.results_opened) as blocker:
        window.findChild(QAction, names.OPEN_RESULTS_ACTION).trigger()
    assert blocker.args == [params]


def test_cancelling_the_dialog_opens_nothing(window, qtbot, monkeypatch):
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    with qtbot.assertNotEmitted(window.results_opened):
        window.findChild(QAction, names.OPEN_RESULTS_ACTION).trigger()


def test_saved_results_open_on_their_recording(window, qtbot, saved):
    recording, params = saved
    files = FileController(window, FakeRecording)

    with qtbot.waitSignal(files.loaded) as blocker:
        files.open_results(params)

    path, source = blocker.args
    assert path == recording.resolve()
    assert isinstance(source, PrecomputedSource)
    assert source.path == recording.resolve()  # what detection needs to run again
    assert source.session.blobs["frame"].tolist() == [0, 1, 1, 2]
    assert source.session.tracking.tracks["track_id"].tolist() == [0, 0, 0]
    assert "sample.czi" in window.windowTitle()


def test_a_moved_recording_is_asked_to_the_user(window, qtbot, saved, tmp_path, monkeypatch):
    recording, params = saved
    moved = tmp_path / "elsewhere" / "renamed.czi"
    moved.parent.mkdir()
    recording.rename(moved)
    asked = []
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", lambda _parent, title, *args: asked.append(title) or (str(moved), "")
    )
    files = FileController(window, FakeRecording)

    with qtbot.waitSignal(files.loaded) as blocker:
        files.open_results(params)

    assert "sample.czi" in asked[0]
    assert blocker.args[0] == moved


def test_a_recording_that_cannot_be_found_is_reported(window, saved, monkeypatch):
    recording, params = saved
    recording.unlink()
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: ("", ""))
    files = FileController(window, FakeRecording)

    files.open_results(params)

    assert "recording sample.czi not found" in status(window)
    assert files.source is None


def test_results_of_another_channel_are_refused(window, qtbot, saved):
    _, params = saved
    opened = []

    def open_channel_1(path):
        opened.append(FakeRecording(path, channel=1))
        return opened[-1]

    files = FileController(window, open_channel_1)
    files.open_results(params)

    qtbot.waitUntil(lambda: "channel 0" in status(window), timeout=5000)
    assert opened[0].closed
    assert files.source is None


def test_a_missing_table_opens_no_recording(window, qtbot, saved, tmp_path):
    _, params = saved
    (tmp_path / "sample_blobs.parquet").unlink()
    opened = []
    files = FileController(window, lambda path: opened.append(path) or FakeRecording(path))

    files.open_results(params)

    qtbot.waitUntil(lambda: "sample_blobs.parquet not found" in status(window), timeout=5000)
    assert opened == []


def test_a_file_that_is_not_saved_results_is_reported(window, tmp_path):
    params = tmp_path / "notes_blobs_params.json"
    params.write_text("not json")
    files = FileController(window, FakeRecording)

    files.open_results(params)

    assert "notes_blobs_params.json is not a valid json file" in status(window)


def test_saved_results_fill_the_pipeline_and_the_view(qtbot, qapp, window, saved):
    _, params = saved
    view = MagicMock()
    controller = MainController(window, qapp, window, open_source=FakeRecording, view=view)

    window.results_opened.emit(params)
    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=5000,
    )
    wait_for_background_tasks()

    for step in (PipelineStep.ROI, PipelineStep.PREPROCESSING, PipelineStep.DETECTION):
        assert controller.pipeline_model.get_status(step) == StepStatus.COMPLETED
    assert controller.pipeline_model.get_step_params(PipelineStep.DETECTION)["threshold"] == 0.25
    assert controller.pipeline_model.get_step_params(PipelineStep.TRACKING)["min_len"] == 2
    assert controller.tracking_result is not None
    assert len(controller.tracking_result.tracks) == 3
    assert view.show_blobs.call_args.args[0].n_points == 1  # the only blob of frame 0

    controller.playback_controller.go_to_frame(1)
    qtbot.waitUntil(lambda: view.show_blobs.call_args.args[0].n_points == 2, timeout=5000)
