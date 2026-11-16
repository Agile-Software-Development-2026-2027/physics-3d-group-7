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
    """
    bins = np.linspace(0.0, 1.0, num_bins + 1)
    if intensities is None or intensities.size == 0:
        return bins, np.zeros(num_bins, dtype=float)

    counts, _ = np.histogram(intensities.ravel(), bins=bins)
    return bins, counts.astype(float)


class PreprocessedIntensityHistogram(IntensityHistogram):
    NUM_BINS: int = 128

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            object_name=names.PREPROC_HISTOGRAM,
            x_units=texts.LABEL_HISTOGRAM_NORMALIZED,
            parent=parent,
        )
        self.apply_theme(self._theme_colors)
        self._recompute_histogram(reset_range=True)

    def apply_computed_data(self, bins: NDArray, counts: NDArray, reset_range: bool = False) -> None:
        """Apply precomputed histogram arrays on the GUI thread."""
        self._curve_item.setData(bins, counts, stepMode="center")
        if reset_range:
            self.reset_zoom()
        self._render_title()
        self._dirty = False
        self._pending_reset_range = False

    @override
    def _recompute_histogram(self, reset_range: bool = False) -> None:
        bins, counts = compute_preprocessed_histogram(self._volume, num_bins=self.NUM_BINS)
        self.apply_computed_data(bins, counts, reset_range=reset_range)

    @override
    def _render_title(self) -> None:
        self._current_title = texts.HISTOGRAM_PREPROC_TITLE
        self.setTitle(self._current_title, color=self._theme_colors.text, size="9pt")
