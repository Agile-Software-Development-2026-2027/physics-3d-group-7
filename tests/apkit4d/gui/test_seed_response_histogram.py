import numpy as np
import pytest

from apkit4d.gui.constants import texts
from apkit4d.gui.views.histograms.seed_response_histogram import SeedResponseHistogram


@pytest.fixture
def histogram(qtbot):
    widget = SeedResponseHistogram()
    qtbot.addWidget(widget)
    return widget


def title(histogram) -> str:
    return histogram.getPlotItem().titleLabel.text


def test_set_threshold_moves_the_line_without_announcing_it(qtbot, histogram) -> None:
    with qtbot.assertNotEmitted(histogram.threshold_changed_by_user):
        histogram.set_threshold(0.3)

    assert histogram.threshold == pytest.approx(0.3)


def test_releasing_the_line_announces_its_position(qtbot, histogram) -> None:
    line = histogram._lo_g_threshold_line
    line.setValue(0.4)

    with qtbot.waitSignal(histogram.threshold_changed_by_user) as blocker:
        line.sigPositionChangeFinished.emit(line)

    assert blocker.args == [pytest.approx(0.4)]


def test_the_title_counts_the_candidates_above_the_threshold(histogram) -> None:
    histogram.set_seeds_response(np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))

    histogram.set_threshold(0.25)

    assert title(histogram) == texts.SEED_HISTOGRAM_TITLE.format(count=2)


def test_moving_the_line_updates_the_count_before_the_release(histogram) -> None:
    histogram.set_seeds_response(np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32))

    histogram._lo_g_threshold_line.setValue(0.35)  # while dragging, no release yet

    assert title(histogram) == texts.SEED_HISTOGRAM_TITLE.format(count=1)


def test_without_data_the_title_invites_to_find_blobs(histogram) -> None:
    assert title(histogram) == texts.SEED_HISTOGRAM_EMPTY

    histogram.set_seeds_response(np.array([0.2], dtype=np.float32))
    histogram.set_seeds_response(None)

    assert title(histogram) == texts.SEED_HISTOGRAM_EMPTY
    assert histogram.seeds_response.size == 0
