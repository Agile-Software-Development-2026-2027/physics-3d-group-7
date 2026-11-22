"""Integration tests for trajectory linking in the GUI pipeline."""

from threading import Event

import pandas as pd
import pytest

from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.tracking.linker import ParticleLinker, TrackingResult


def _prepare_tracking(controller: MainController) -> None:
    """Complete prerequisite stages before tracking."""
    detections = pd.DataFrame(
        {
            "frame": list(range(6)),
            "z_um": [0.0] * 6,
            "y_um": [0.0] * 6,
            "x_um": [float(i) for i in range(6)],
        }
    )

    controller.pipeline_model.set_batch_results(
        detections,
        {"info": {"dt_s": 0.5}},
    )

    for step in (
        PipelineStep.ROI,
        PipelineStep.PREPROCESSING,
        PipelineStep.DETECTION,
    ):
        controller.pipeline_controller.complete_stage(step)
    controller._window.right_panel.set_stages_enabled(True)


def test_tracking_pipeline_completes(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    _prepare_tracking(controller)

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    result = controller.tracking_result
    assert isinstance(result, TrackingResult)
    assert result.metadata["num_detections"] == 6
    assert result.metadata["num_tracks_retained"] >= 1
    assert not result.tracks.empty


def test_tracking_pipeline_handles_failure(qtbot, qapp, monkeypatch) -> None:
    def failing_link(_self, _detections, **_kwargs):
        raise RuntimeError("Tracking failure")

    monkeypatch.setattr(ParticleLinker, "link", failing_link)

    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    _prepare_tracking(controller)

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: window.right_panel.bottom_stats.summary_label.text() == "Trajectory linking failed",
        timeout=10000,
    )

    assert controller.tracking_result is None
    assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert "Tracking failure" in (window.right_panel.bottom_stats.details_label.text())


@pytest.mark.parametrize("action", ["change_params", "reset_pipeline"])
def test_tracking_ignores_stale_result(qtbot, qapp, monkeypatch, action) -> None:
    started = Event()
    release = Event()
    original_link = ParticleLinker.link

    def slow_link(self, detections, **kwargs):
        if self.config.min_len == 5:
            started.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Tracking test timed out")

        result = original_link(self, detections, **kwargs)
        result.metadata["used_min_len"] = self.config.min_len
        return result

    monkeypatch.setattr(ParticleLinker, "link", slow_link)

    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    _prepare_tracking(controller)

    try:
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)
        qtbot.waitUntil(started.is_set, timeout=5000)

        if action == "change_params":
            controller.pipeline_model.update_step_params(PipelineStep.TRACKING, min_len=7)
        else:
            controller.pipeline_controller.reset_pipeline()
    finally:
        release.set()

    qtbot.waitUntil(
        lambda: not controller._tracking_controller.is_running,
        timeout=10000,
    )

    result = controller.tracking_result

    if action == "reset_pipeline":
        assert result is None
        assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    else:
        assert result is not None
        assert result.metadata["used_min_len"] == 7
        assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED


def test_tracking_restarts_after_reset_with_same_params(qtbot, qapp, monkeypatch) -> None:
    """A result from before reset must not complete the new run."""
    started = Event()
    release = Event()
    original_link = ParticleLinker.link
    calls = 0

    def controlled_link(self, detections, **kwargs):
        nonlocal calls
        calls += 1
        run_number = calls

        if run_number == 1:
            started.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Tracking test timed out")

        result = original_link(self, detections, **kwargs)
        result.metadata["run_number"] = run_number
        return result

    monkeypatch.setattr(ParticleLinker, "link", controlled_link)

    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    _prepare_tracking(controller)

    try:
        # Start first tracking task and keep it running.
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)
        qtbot.waitUntil(started.is_set, timeout=5000)

        # Reset and start tracking again with identical parameters.
        controller.pipeline_controller.reset_pipeline()
        _prepare_tracking(controller)
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    finally:
        release.set()

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    result = controller.tracking_result
    assert result is not None
    assert result.metadata["run_number"] == 2
    assert calls == 2


def test_tracking_play_button_starts_linking(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    _prepare_tracking(controller)

    play_button = window.right_panel.get_play_button(PipelineStep.TRACKING)
    assert play_button is not None

    play_button.click()

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert isinstance(controller.tracking_result, TrackingResult)


def test_tracking_uses_stored_detections(qtbot, qapp) -> None:
    """Tracking should use detections stored in the pipeline model."""
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    _prepare_tracking(controller)

    detections = pd.DataFrame(
        {
            "frame": list(range(8)),
            "z_um": [0.0] * 8,
            "y_um": [0.0] * 8,
            "x_um": [float(i) for i in range(8)],
        }
    )

    controller.pipeline_model.set_batch_results(
        detections,
        {"info": {"dt_s": 0.5}},
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    result = controller.tracking_result
    assert result is not None
    assert result.metadata["num_detections"] == 8


def test_tracking_requires_real_detections(qtbot, qapp, monkeypatch) -> None:
    """Tracking must not use synthetic data or rerun detection."""
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    for step in (
        PipelineStep.ROI,
        PipelineStep.PREPROCESSING,
        PipelineStep.DETECTION,
    ):
        controller.pipeline_controller.complete_stage(step)
    controller._window.right_panel.set_stages_enabled(True)

    def forbidden(*args, **kwargs):
        raise AssertionError("Tracking must not recompute detections")

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        forbidden,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    assert controller.tracking_result is None
    assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert "No detections available" in (window.right_panel.bottom_stats.details_label.text())
