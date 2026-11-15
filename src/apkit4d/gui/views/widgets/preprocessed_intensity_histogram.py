from typing import override

import numpy as np
from numpy.typing import NDArray
from PySide6.QtWidgets import QWidget

from apkit4d.gui.constants import names, texts
from apkit4d.gui.views.widgets.intensity_histogram import IntensityHistogram

__all__ = ["PreprocessedIntensityHistogram", "compute_preprocessed_histogram"]


def compute_preprocessed_histogram(
    intensities: NDArray | None,
    num_bins: int = 128,
) -> tuple[NDArray, NDArray]:
    """
    Compute a uniform histogram of preprocessed intensities over [0.0, 1.0].

    Args:
        intensities: Preprocessed voxel array, or None.
        num_bins: Number of equal bins across [0.0, 1.0], default 128.

    Returns:
        Tuple of (bins, counts) with shapes (num_bins + 1,) and (num_bins,).
    """
    bins = np.linspace(0.0, 1.0, num_bins + 1)
    if intensities is None or intensities.size == 0:
        return bins, np.zeros(num_bins, dtype=float)

    counts, _ = np.histogram(intensities.ravel(), bins=bins)
    return bins, counts.astype(float)


class PreprocessedIntensityHistogram(IntensityHistogram):
    """
    Non-interactive PyQtGraph histogram showing the voxel intensity distribution
    of the ROI volume after the preprocessing pipeline.

    The X axis plots intensities in [0, 1] divided into 128 equal bins.
    The Y axis shows voxel frequency on a logarithmic scale.
    """

    NUM_BINS: int = 128

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            object_name=names.PREPROC_HISTOGRAM,
            x_units=texts.LABEL_HISTOGRAM_NORMALIZED,
            parent=parent,
        )
        self.apply_theme(self._theme_colors)
        self._recompute_histogram(reset_range=True)

    @override
    def _recompute_histogram(self, reset_range: bool = False) -> None:
        bins, counts = compute_preprocessed_histogram(self._volume, num_bins=self.NUM_BINS)
        self._curve_item.setData(bins, counts, stepMode="center")
        if reset_range:
            self.reset_zoom()
        self._render_title()
        self._dirty = False
        self._pending_reset_range = False

    @override
    def _render_title(self) -> None:
        self._current_title = texts.HISTOGRAM_PREPROC_TITLE
        self.setTitle(self._current_title, color=self._theme_colors.text, size="9pt")
