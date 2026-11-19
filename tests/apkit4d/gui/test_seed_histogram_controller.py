from typing import cast

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal

from apkit4d.gui.controllers.blob_detection_controller import BlobDetectionController
from apkit4d.gui.controllers.seed_histogram_controller import SeedHistogramController
from apkit4d.gui.views.histograms.seed_response_histogram import SeedResponseHistogram
from apkit4d.gui.views.stages.blob_detection_inspector import BlobDetectionInspector


class FakeBlobController(QObject):
    seeds_response_changed = Signal(object)


@pytest.fixture
def setup(qtbot, monkeypatch):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)
    inspector.lo_g_threshold = 0.1  # what BlobDetectionController sets at the start
    histogram = SeedResponseHistogram()
    qtbot.addWidget(histogram)
    blob_controller = cast(BlobDetectionController, FakeBlobController())
    controller = SeedHistogramController(histogram, inspector, blob_controller)
    return inspector, histogram, blob_controller, controller


def test_the_histogram_starts_from_the_value_of_the_inspector(setup) -> None:
    _, histogram, _, _ = setup
    assert histogram.threshold == pytest.approx(0.1)


def test_the_spinbox_moves_the_line(setup) -> None:
    inspector, histogram, _, _ = setup
    inspector._lo_g_threshold.setValue(0.3)
    assert histogram.threshold == pytest.approx(0.3)


def test_releasing_the_line_sets_the_spinbox(setup) -> None:
    inspector, histogram, _, _ = setup
    histogram.threshold_changed_by_user.emit(0.3)
    assert inspector.lo_g_threshold == pytest.approx(0.3)


@pytest.mark.parametrize("released, kept", [(0.1234, 0.12), (7.0, 5.0)])
def test_the_line_snaps_to_what_the_spinbox_keeps(setup, released, kept) -> None:
    inspector, histogram, _, _ = setup

    histogram.threshold_changed_by_user.emit(released)

    assert inspector.lo_g_threshold == pytest.approx(kept)
    assert histogram.threshold == pytest.approx(kept)


def test_a_release_changes_the_threshold_once(setup) -> None:
    inspector, histogram, _, _ = setup
    changes: list[float] = []
    inspector.lo_g_changed.connect(changes.append)

    histogram.threshold_changed_by_user.emit(0.3)

    assert changes == [pytest.approx(0.3)]  # no echo back from the histogram


def test_the_response_of_a_detection_reaches_the_histogram(setup) -> None:
    _, histogram, blob_controller, _ = setup
    values = np.array([0.2, 0.4], dtype=np.float32)

    blob_controller.seeds_response_changed.emit(values)
    assert np.array_equal(histogram.seeds_response, values)

    blob_controller.seeds_response_changed.emit(None)
    assert histogram.seeds_response.size == 0
