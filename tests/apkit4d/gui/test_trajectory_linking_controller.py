"""Tests for asynchronous trajectory linking."""

import pandas as pd

from apkit4d.core.models import TrackingConfig
from apkit4d.gui.controllers.trajectory_linking_controller import (
    TrajectoryLinkingController,
)
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
