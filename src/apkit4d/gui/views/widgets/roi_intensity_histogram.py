"""
Interactive intensity histogram widget for ROI volume distribution.

Plots the distribution of voxel intensities in the currently active Region of Interest (ROI)
using PyQtGraph with a logarithmic counts scale and interactive vertical threshold lines.
"""

from typing import Final, override

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from apkit4d.gui.constants import names, texts
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, ThemeColors


def compute_intensity_histogram(
    intensities: NDArray | None,
    lowest_intensity: float,
    num_bins: int = 256,
    p9999: float | None = None,
) -> tuple[NDArray, NDArray, float]:
    """
    Compute a uniform histogram of intensities over the range [0, top].

    Top is defined as max(1.3 * lowest_intensity, 99.99th percentile of nonzero voxels).

    Args:
        intensities: Array of voxel intensities, or None.
        lowest_intensity: Lower bound intensity threshold.
        num_bins: Number of uniform bins across [0, top], default 256.
        p9999: Optional precomputed 99.99th percentile of nonzero voxels. Computed when None.

    Returns:
        tuple of (bins, counts, top) where:
            bins: array of shape (num_bins + 1,) containing the bin edges.
            counts: array of shape (num_bins,) containing voxel counts.
            top: the upper bound of the histogram range in arbitrary units (AU).
    """

    if intensities is None or intensities.size == 0:
        top = max(1.3 * float(lowest_intensity), 1.0)
        bins = np.linspace(0.0, top, num_bins + 1)
        counts = np.zeros(num_bins, dtype=float)
        return bins, counts, top

    flat = intensities.ravel()
    if p9999 is None:  # cached percentile
        nonzero = flat[flat > 0]
        p9999 = float(np.percentile(nonzero, 99.99)) if nonzero.size > 0 else 0.0

    top = max(1.3 * float(lowest_intensity), p9999)
    if top <= 0.0:
        top = 1.0

    bins = np.linspace(0.0, top, num_bins + 1)
    counts, _ = np.histogram(flat, bins=bins)
    return bins, counts.astype(float), top


def compute_fraction_saturated(intensities: NDArray | None, highest_intensity: float) -> float:
    """
    Calculate the fraction of intensities that are above or equal to highest_intensity.

    Args:
        intensities: Array of voxel intensities, or None.
        highest_intensity: Upper bound intensity threshold.

    Returns:
        Fraction of saturated voxels as a float in [0.0, 1.0].
    """

    if intensities is None or intensities.size == 0:
        return 0.0
    return float((intensities >= highest_intensity).mean())


class RoiIntensityHistogram(pg.PlotWidget):
    """
    Interactive PyQtGraph histogram showing the intensity distribution of the current ROI volume.

    The X axis shows the magnitudes of the intensities in arbitrary units (AU) from 0 to top.
    The Y axis shows the voxel count for each magnitude, it has logarithmic scale.

    There are two draggable vertical lines representing the lowest_intensity and hightest_intensity,
    used as the normalization window bounds during preprocessing.

    Signals:
        lowest_intensity_changed: Emitted with new float value when lowest_intensity line is moved.
        highest_intensity_changed: Emitted with new float value when highest_intensity line is moved.
    """

    NUM_BINS: Final[int] = 256

    lowest_intensity_changed = Signal(float)
    highest_intensity_changed = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName(names.ROI_HISTOGRAM)
        self.setMinimumHeight(200)
        self.setMaximumHeight(280)

        self._volume: NDArray | None = None
        self._lowest_intensity: float = 0.0
        self._highest_intensity: float = 1000.0
        self._normalization_enabled: bool = True
        self._p9999: float = 0.0
        self._top: float = 1.0
        self._frac_sat: float = 0.0
        self._current_title: str = ""
        self._theme_colors: ThemeColors = THEME_COLORS[DEFAULT_THEME]

        plot_item = self.getPlotItem()
        plot_item.hideButtons()  # hide the defaults buttons
        plot_item.setMenuEnabled(True)  # right click menu, why not
        self.setLogMode(x=False, y=True)
        self.setLabel("bottom", texts.LABEL_HISTOGRAM_INTENSITY, units=texts.LABEL_HISTOGRAM_AU)
        self.setLabel("left", texts.LABEL_HISTOGRAM_COUNTS)

        bins = np.linspace(0.0, 1.0, self.NUM_BINS + 1)
        counts = np.zeros(self.NUM_BINS, dtype=float)
        self._curve_item = self.plot(bins, counts, stepMode="center", fillLevel=0)

        self._lowest_line = pg.InfiniteLine(
            pos=self._lowest_intensity,
            angle=90,
            movable=True,
            bounds=[0.0, None],
        )
        self._lowest_line.setZValue(10)
        self._lowest_line.setToolTip(texts.ROI_INTENSITIES_MIN_LINE)
        self._highest_line = pg.InfiniteLine(
            pos=self._highest_intensity,
            angle=90,
            movable=True,
            bounds=[0.0, None],
        )
        self._highest_line.setZValue(10)
        self._highest_line.setToolTip(texts.ROI_INTENSITIES_MAX_LINE)
        self.addItem(self._lowest_line)
        self.addItem(self._highest_line)

        self._lowest_line.sigDragged.connect(self._on_lowest_dragged)
        self._lowest_line.sigPositionChangeFinished.connect(self._on_lowest_dragged)
        self._highest_line.sigDragged.connect(self._on_highest_dragged)
        self._highest_line.sigPositionChangeFinished.connect(self._on_highest_dragged)

        self.apply_theme(self._theme_colors)
        self._recompute_histogram()

    @property
    def volume(self) -> NDArray | None:
        """The voxel volume currently displayed."""
        return self._volume

    @property
    def lowest_intensity(self) -> float:
        """Current lowest intensity threshold."""
        return self._lowest_intensity

    @property
    def highest_intensity(self) -> float:
        """Current highest intensity threshold."""
        return self._highest_intensity

    @property
    def normalization_enabled(self) -> bool:
        """Whether intensity normalization is enabled."""
        return self._normalization_enabled

    @property
    def frac_sat(self) -> float:
        """Fraction of intensities at or above the highest intensity bound."""
        return self._frac_sat

    @property
    def title_text(self) -> str:
        return self._current_title

    @property
    def lowest_line(self) -> pg.InfiniteLine:
        return self._lowest_line

    @property
    def highest_line(self) -> pg.InfiniteLine:
        return self._highest_line

    def set_volume(self, volume: NDArray | None) -> None:
        """
        Update the voxel intensity volume and refresh the histogram.

        Args:
            volume: 3D or flattened voxel array, or None if no volume is open.
        """

        self._volume = volume
        if volume is not None and volume.size > 0:
            flat = volume.ravel()
            nonzero = flat[flat > 0]
            self._p9999 = float(np.percentile(nonzero, 99.99)) if nonzero.size > 0 else 0.0
        else:
            self._p9999 = 0.0

        self._recompute_histogram(reset_range=True)

    def set_intensity_bounds(self, lowest: float, highest: float) -> None:
        """
        Sets vertical threshold line positions programmatically without emitting drag signals.

        Args:
            lowest: New lowest_intensity value in arbitrary units.
            highest: New highest_intensity value in arbitrary units.
        """

        self._lowest_intensity = float(lowest)
        self._highest_intensity = float(highest)

        with QSignalBlocker(self._lowest_line):
            self._lowest_line.setValue(self._lowest_intensity)
        with QSignalBlocker(self._highest_line):
            self._highest_line.setValue(self._highest_intensity)

        self._recompute_histogram()

    def set_normalization_enabled(self, enabled: bool) -> None:
        self._normalization_enabled = enabled

    def _on_lowest_dragged(self, line: pg.InfiniteLine) -> None:
        val = max(0.0, round(float(line.value()), 1))
        if val == self._lowest_intensity:
            return
        self._lowest_intensity = val
        self._recompute_histogram()
        self.lowest_intensity_changed.emit(val)

    def _on_highest_dragged(self, line: pg.InfiniteLine) -> None:
        val = max(0.0, round(float(line.value()), 1))
        if val == self._highest_intensity:
            return
        self._highest_intensity = val
        self._update_frac_sat_and_title()
        self.highest_intensity_changed.emit(val)

    def _recompute_histogram(self, reset_range: bool = False) -> None:
        """
        Args:
            reset_range (bool): whether to reset zoom and position of the axes
        """
        bins, counts, top = compute_intensity_histogram(
            self._volume, self._lowest_intensity, num_bins=self.NUM_BINS, p9999=self._p9999
        )
        self._top = top
        self._curve_item.setData(bins, counts, stepMode="center")
        if reset_range:
            self.reset_zoom()
        self._update_frac_sat_and_title()

    def _update_frac_sat_and_title(self) -> None:
        self._frac_sat = compute_fraction_saturated(self._volume, self._highest_intensity)
        self._render_title()

    def apply_theme(self, colors: ThemeColors) -> None:
        """
        Update background, axes, curve, and threshold line colors to match theme.

        Args:
            colors: Theme color palette.
        """

        self._theme_colors = colors
        self.setBackground(colors.base)

        axis_pen = pg.mkPen(color=colors.text, width=1)
        text_pen = pg.mkPen(color=colors.text)

        bottom_axis = self.getAxis("bottom")
        bottom_axis.setPen(axis_pen)
        bottom_axis.setTextPen(text_pen)

        left_axis = self.getAxis("left")
        left_axis.setPen(axis_pen)
        left_axis.setTextPen(text_pen)

        # curve
        curve_pen = pg.mkPen(color=colors.highlight, width=1.5)
        c = QColor(colors.highlight)
        c.setAlpha(90)
        curve_brush = pg.mkBrush(c)
        self._curve_item.setPen(curve_pen)
        self._curve_item.setBrush(curve_brush)

        # different colors for the threshold lines
        is_dark = colors.base == "#2b2d31"
        lowest_color = "#e5c07b" if is_dark else "#b45309"
        highest_color = "#e06c75" if is_dark else "#dc2626"

        self._lowest_line.setPen(pg.mkPen(color=lowest_color, width=2, style=Qt.PenStyle.DashLine))
        self._lowest_line.setHoverPen(pg.mkPen(color=lowest_color, width=4))

        self._highest_line.setPen(pg.mkPen(color=highest_color, width=2, style=Qt.PenStyle.DashLine))
        self._highest_line.setHoverPen(pg.mkPen(color=highest_color, width=4))

        self._render_title()

    def _render_title(self) -> None:
        title = texts.HISTOGRAM_ROI_TITLE.format(frac_sat=self._frac_sat)
        self._current_title = title
        self.setTitle(title, color=self._theme_colors.text, size="9pt")

    @override
    def mouseDoubleClickEvent(self, event) -> None:
        self.reset_zoom()
        super().mouseDoubleClickEvent(event)

    def reset_zoom(self) -> None:
        self.getViewBox().setXRange(0.0, self._top, padding=None)
        self.enableAutoRange(axis="y")
