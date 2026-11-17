"""Integration tests for detection and tracking."""

from threading import Event
from unittest.mock import MagicMock

import pandas as pd

from apkit4d.blob_detection import BlobParams
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.trajectory_detection import DetectionData
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziSource


def _controller(qtbot, qapp):
    window = MainWindow()
    qtbot.addWidget(window)

    controller = MainController(window, qapp)
    source = MagicMock(spec=CziSource)

    controller.file_controller._source = source
    controller.pipeline_controller.complete_stage(PipelineStep.ROI)
    controller.pipeline_controller.complete_stage(PipelineStep.PREPROCESSING)

    return controller, source


def _detections():
    return pd.DataFrame(
        {
            "frame": list(range(8)),
            "z_um": [0.0] * 8,
            "y_um": [0.0] * 8,
            "x_um": [float(i) for i in range(8)],
        }
    )


def test_detection_feeds_tracking_without_recalculation(qtbot, qapp, monkeypatch):
    controller, source = _controller(qtbot, qapp)
    calls = []
    detections = _detections()

    def fake_detect(czi, preproc, blob, roi):
        calls.append((czi, preproc, blob, roi))
        return DetectionData(
            detections,
            0.5,
            {"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(
        "apkit4d.gui.controllers.main_controller.detect_sequence",
        fake_detect,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert len(calls) == 1
    assert calls[0][0] is source
    assert calls[0][2] == BlobParams()
    assert calls[0][3] is None

    pd.testing.assert_frame_equal(
        controller.pipeline_model.batch_results[0],
        detections,
    )

    assert controller.tracking_result.metadata["num_detections"] == 8

    # Tracking parameters change, but detection must not rerun.
    controller.pipeline_model.update_step_params(
        PipelineStep.TRACKING,
        min_len=7,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert len(calls) == 1
    assert controller.tracking_result.metadata["num_detections"] == 8


def test_detection_failure_stops_pipeline(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)

    def fake_detect(*args, **kwargs):
        raise RuntimeError("Detection failed in test")

    monkeypatch.setattr(
        "apkit4d.gui.controllers.main_controller.detect_sequence",
        fake_detect,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE,
        timeout=10000,
    )

    assert controller.pipeline_model.batch_results is None
    assert controller.tracking_result is None

    assert "Detection failed in test" in (controller._window.right_panel.bottom_stats.details_label.text())


def test_detection_ignores_result_after_reset(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)
    started, release = Event(), Event()

    def fake_detect(*args, **kwargs):
        started.set()

        if not release.wait(timeout=10):
            raise TimeoutError("Detection test timed out")

        return DetectionData(
            _detections(),
            0.5,
            {"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(
        "apkit4d.gui.controllers.main_controller.detect_sequence",
        fake_detect,
    )

    try:
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

        qtbot.waitUntil(
            started.is_set,
            timeout=5000,
        )

        controller.pipeline_controller.reset_pipeline()

    finally:
        release.set()

    qtbot.waitUntil(
        lambda: controller._detection_task is None,
        timeout=10000,
    )

    assert controller.pipeline_model.batch_results is None
    assert controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE


def test_detection_reuses_stored_results(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)

    controller.pipeline_model.set_batch_results(
        _detections(),
        {"info": {"dt_s": 0.5}},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Sequence detection was run again")

    monkeypatch.setattr(
        "apkit4d.gui.controllers.main_controller.detect_sequence",
        forbidden,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert controller.tracking_result.metadata["num_detections"] == 8


def test_detection_restarts_when_parameters_change(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)
    started, release = Event(), Event()
    thresholds = []

    def fake_detect(czi, preproc, blob, roi):
        thresholds.append(blob.threshold)

        if len(thresholds) == 1:
            started.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Detection test timed out")

        return DetectionData(
            _detections(),
            0.5,
            {"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(
        "apkit4d.gui.controllers.main_controller.detect_sequence",
        fake_detect,
    )

    try:
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

        qtbot.waitUntil(
            started.is_set,
            timeout=5000,
        )

        controller.pipeline_model.update_step_params(
            PipelineStep.DETECTION,
            threshold=0.6,
        )

    finally:
        release.set()

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert thresholds == [BlobParams().threshold, 0.6]
    assert controller.tracking_result.metadata["num_detections"] == 8
