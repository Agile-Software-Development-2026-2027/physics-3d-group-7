from unittest.mock import patch

import numpy as np
import pytest

from apkit4d.gui.constants import names, texts
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.histograms.preprocessed_intensity_histogram import (
    PreprocessedIntensityHistogram,
    compute_preprocessed_histogram,
)


def test_compute_preprocessed_histogram_empty_or_none() -> None:
    bins, counts = compute_preprocessed_histogram(None, num_bins=128)
    assert len(bins) == 129
    assert len(counts) == 128
    assert bins[0] == pytest.approx(0.0)
    assert bins[-1] == pytest.approx(1.0)
    assert np.all(counts == 0.0)

    bins_e, counts_e = compute_preprocessed_histogram(np.array([], dtype=np.float32), num_bins=128)
    assert len(bins_e) == 129
    assert len(counts_e) == 128
    assert np.all(counts_e == 0.0)


def test_compute_preprocessed_histogram_bins_unit_interval() -> None:
    # 128 values centered in each of the 128 equal bins over [0, 1]
    centers = (np.arange(128, dtype=np.float32) + 0.5) / 128.0
    bins, counts = compute_preprocessed_histogram(centers, num_bins=128)

    assert len(bins) == 129
    assert len(counts) == 128
    assert np.all(counts == 1.0)


def test_preprocessed_histogram_widget_init(qtbot) -> None:
    widget = PreprocessedIntensityHistogram()
    qtbot.addWidget(widget)

    assert widget.objectName() == names.PREPROC_HISTOGRAM
    assert widget.NUM_BINS == 128
    assert widget.volume is None
    assert widget.title_text == texts.HISTOGRAM_PREPROC_TITLE
    assert not hasattr(widget, "lowest_line")
    assert not hasattr(widget, "highest_line")


def test_preprocessed_histogram_set_volume_updates_curve(qtbot) -> None:
    widget = PreprocessedIntensityHistogram()
    qtbot.addWidget(widget)
    widget.set_expanded(True)

    vol = np.linspace(0.0, 1.0, 1000, dtype=np.float32).reshape((10, 10, 10))
    widget.set_volume(vol)

    assert widget.volume is vol
    x_data, y_data = widget._curve_item.getData()
    assert len(x_data) == 129
    assert len(y_data) == 128
    # PlotWidget has logMode y=True, so curve y_data is log10(counts)
    assert np.sum(10.0**y_data) == pytest.approx(1000.0)


def test_preprocessed_histogram_defers_recomputation_when_collapsed(qtbot) -> None:
    widget = PreprocessedIntensityHistogram()
    qtbot.addWidget(widget)

    vol = np.linspace(0.0, 1.0, 1000, dtype=np.float32)
    with patch(
        "apkit4d.gui.views.histograms.preprocessed_intensity_histogram.compute_preprocessed_histogram",
        wraps=compute_preprocessed_histogram,
    ) as mock_compute:
        widget.set_volume(vol)

        assert widget.volume is vol
        assert mock_compute.call_count == 0

        widget.set_expanded(True)
        assert mock_compute.call_count == 1

        widget.set_expanded(True)
        assert mock_compute.call_count == 1


def test_preprocessed_histogram_apply_theme(qtbot) -> None:
    widget = PreprocessedIntensityHistogram()
    qtbot.addWidget(widget)

    widget.apply_theme(DARK_COLORS)
    assert widget.backgroundBrush().color().name().lower() == DARK_COLORS.raised_base.lower()
    assert widget._curve_item.opts["pen"].color().name().lower() == DARK_COLORS.highlight.lower()

    widget.apply_theme(LIGHT_COLORS)
    assert widget.backgroundBrush().color().name().lower() == LIGHT_COLORS.raised_base.lower()
    assert widget._curve_item.opts["pen"].color().name().lower() == LIGHT_COLORS.highlight.lower()
