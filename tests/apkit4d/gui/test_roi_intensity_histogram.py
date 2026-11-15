"""
Unit tests for RoiIntensityHistogram widget and calculation helpers.
"""

import numpy as np
import pytest

from apkit4d.gui.constants import names, texts
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.widgets.roi_intensity_histogram import (
    RoiIntensityHistogram,
    compute_fraction_saturated,
    compute_intensity_histogram,
)


def test_compute_intensity_histogram_empty_or_none() -> None:
    bins, counts, top = compute_intensity_histogram(None, lowest_intensity=10.0, num_bins=256)
    assert len(bins) == 257
    assert len(counts) == 256
    assert np.all(counts == 0.0)
    assert top == pytest.approx(13.0)
    assert bins[0] == 0.0
    assert bins[-1] == top

    empty = np.array([], dtype=np.uint16)
    bins_e, counts_e, top_e = compute_intensity_histogram(empty, lowest_intensity=0.0, num_bins=256)
    assert top_e == pytest.approx(1.0)
    assert len(bins_e) == 257
    assert len(counts_e) == 256


def test_compute_intensity_histogram_with_nonzero_voxels() -> None:
    data = np.arange(10001, dtype=np.uint16)
    bins, counts, top = compute_intensity_histogram(data, lowest_intensity=50.0, num_bins=256)
    assert len(bins) == 257
    assert len(counts) == 256
    # 99.99th percentile of 1..10000 is ~10000, which is > 1.3 * 50
    assert top == pytest.approx(10000.0, rel=1e-2)
    assert counts.sum() == pytest.approx(10000.0)


def test_compute_intensity_histogram_lowest_intensity_dominates() -> None:
    # If lowest_intensity is 2000, 1.3 * 2000 = 2600 > 99.99th percentile of 1000
    data = np.arange(1001, dtype=np.uint16)
    bins, counts, top = compute_intensity_histogram(data, lowest_intensity=2000.0, num_bins=256)
    assert top == pytest.approx(2600.0)
    assert len(bins) == 257


def test_compute_fraction_saturated() -> None:
    assert compute_fraction_saturated(None, 100.0) == 0.0
    assert compute_fraction_saturated(np.array([]), 100.0) == 0.0

    data = np.arange(100, dtype=np.uint16)
    # voxels >= 80 are 20 out of 100 -> 0.20
    frac = compute_fraction_saturated(data, 80.0)
    assert frac == pytest.approx(0.20)


def test_histogram_widget_init(qtbot) -> None:
    widget = RoiIntensityHistogram()
    qtbot.addWidget(widget)

    assert widget.objectName() == names.ROI_HISTOGRAM
    assert widget.lowest_intensity == 0.0
    assert widget.highest_intensity == 1000.0
    assert widget.lowest_line is not None
    assert widget.highest_line is not None
    assert widget.lowest_line.movable
    assert widget.highest_line.movable
    assert widget._top > 0.0


def test_histogram_set_volume_updates_data_and_title(qtbot) -> None:
    widget = RoiIntensityHistogram()
    qtbot.addWidget(widget)

    vol = np.arange(1000, dtype=np.uint16).reshape((10, 10, 10))
    widget.set_intensity_bounds(lowest=100.0, highest=800.0)
    widget.set_volume(vol)

    assert widget.volume is vol
    # 200 out of 1000 voxels >= 800 -> 0.20
    assert widget.frac_sat == pytest.approx(0.20)
    expected_title = texts.HISTOGRAM_ROI_TITLE.format(frac_sat=0.20)
    assert widget.title_text == expected_title


def test_histogram_set_intensity_bounds(qtbot) -> None:
    widget = RoiIntensityHistogram()
    qtbot.addWidget(widget)

    vol = np.arange(1000, dtype=np.uint16)
    widget.set_volume(vol)
    widget.set_intensity_bounds(lowest=200.0, highest=500.0)

    assert widget.lowest_intensity == pytest.approx(200.0)
    assert widget.highest_intensity == pytest.approx(500.0)
    assert widget.lowest_line.value() == pytest.approx(200.0)
    assert widget.highest_line.value() == pytest.approx(500.0)
    assert widget.frac_sat == pytest.approx(0.50)


def test_histogram_dragging_lines_emits_signals(qtbot) -> None:
    widget = RoiIntensityHistogram()
    qtbot.addWidget(widget)

    vol = np.arange(1000, dtype=np.uint16)
    widget.set_volume(vol)

    with qtbot.waitSignal(widget.lowest_intensity_changed, timeout=1000) as blocker:
        widget.lowest_line.setValue(150.0)
        widget.lowest_line.sigDragged.emit(widget.lowest_line)
    assert blocker.args == [150.0]
    assert widget.lowest_intensity == pytest.approx(150.0)

    with qtbot.waitSignal(widget.highest_intensity_changed, timeout=1000) as blocker:
        widget.highest_line.setValue(700.0)
        widget.highest_line.sigDragged.emit(widget.highest_line)
    assert blocker.args == [700.0]
    assert widget.highest_intensity == pytest.approx(700.0)
    assert widget.frac_sat == pytest.approx(0.30)


def test_histogram_apply_theme(qtbot) -> None:
    widget = RoiIntensityHistogram()
    qtbot.addWidget(widget)

    widget.apply_theme(DARK_COLORS)
    assert widget.lowest_line.pen.color().name().lower() == "#e5c07b"

    widget.apply_theme(LIGHT_COLORS)
    assert widget.lowest_line.pen.color().name().lower() == "#b45309"


def test_set_normalization_enabled(qtbot) -> None:
    widget = RoiIntensityHistogram()
    qtbot.addWidget(widget)

    assert widget.normalization_enabled
    widget.set_normalization_enabled(False)
    assert not widget.normalization_enabled
