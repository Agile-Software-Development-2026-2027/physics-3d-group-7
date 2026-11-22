"""Tests for asynchronous trajectory linking."""

from unittest.mock import MagicMock

import pandas as pd

from apkit4d.core.models import TrackingConfig
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.trajectory_linking_controller import (
    TrajectoryLinkingController,
)
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep, StepStatus
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.tracking.linker import TrackingResult


def make_detections() -> pd.DataFrame:
    """Create a synthetic particle moving across six frames."""
    return pd.DataFrame(
        {
            "frame": list(range(6)),
            "z_um": [0.0] * 6,
            "y_um": [0.0] * 6,
            "x_um": [float(i) for i in range(6)],
        }
    )


def test_tracking_success(qtbot) -> None:
    controller = TrajectoryLinkingController()

    with qtbot.waitSignal(controller.result_ready, timeout=10000):
        started = controller.run(make_detections(), TrackingConfig())
        assert started
        assert controller.is_running

    assert not controller.is_running
    assert isinstance(controller.result, TrackingResult)
    assert controller.result.metadata["num_detections"] == 6
    assert not controller.result.tracks.empty


def test_tracking_failure(qtbot) -> None:
    controller = TrajectoryLinkingController()

    # Non-empty input with a missing required column
    invalid_detections = pd.DataFrame({"frame": [0], "x_um": [1.0]})

    with qtbot.waitSignal(controller.failed, timeout=10000) as blocker:
        assert controller.run(invalid_detections, TrackingConfig())

    assert isinstance(blocker.args[0], ValueError)
    assert not controller.is_running
    assert controller.result is None


def test_tracking_cannot_start_twice(qtbot) -> None:
    controller = TrajectoryLinkingController()
    detections = make_detections()

    with qtbot.waitSignal(controller.result_ready, timeout=10000):
        assert controller.run(detections, TrackingConfig())
        assert not controller.run(detections, TrackingConfig())

    assert not controller.is_running


def test_tracking_controller_orchestrates_stage_4_standalone(qtbot) -> None:
    """TrajectoryLinkingController runs Stage 4 directly without MainController."""
    panel = RightPanel()
    qtbot.addWidget(panel)
    model = PipelineModel()
    pipeline = PipelineController(model, panel)
    traj_ctrl = MagicMock()

    controller = TrajectoryLinkingController(
        pipeline_model=model,
        pipeline_controller=pipeline,
        trajectory_controller=traj_ctrl,
    )

    model.set_batch_results(make_detections(), {"info": {"dt_s": 0.5}})
    for step in (PipelineStep.ROI, PipelineStep.PREPROCESSING, PipelineStep.DETECTION):
        pipeline.complete_stage(step)

    pipeline.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(lambda: model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED, timeout=10000)
    assert isinstance(controller.result, TrackingResult)
    traj_ctrl.set_trajectories.assert_called_once()


def test_tracking_controller_fails_gracefully_without_detections(qtbot) -> None:
    """Running Stage 4 without batch_results resets status to IDLE and reports failure."""
    panel = RightPanel()
    qtbot.addWidget(panel)
    model = PipelineModel()
    pipeline = PipelineController(model, panel)

    controller = TrajectoryLinkingController(
        pipeline_model=model,
        pipeline_controller=pipeline,
    )

    for step in (PipelineStep.ROI, PipelineStep.PREPROCESSING, PipelineStep.DETECTION):
        pipeline.complete_stage(step)

    pipeline.run_up_to(PipelineStep.TRACKING)

    assert controller.result is None
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert panel.bottom_stats.summary_label.text() == "Trajectory linking failed"
    assert "No detections available" in panel.bottom_stats.details_label.text()
