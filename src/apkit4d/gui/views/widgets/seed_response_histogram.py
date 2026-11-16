from math import ceil
from typing import override

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from apkit4d.blob_detection import BlobParams
from apkit4d.gui.constants import texts
from apkit4d.gui.theme import ThemeColors


class SeedResponseHistogram(pg.PlotWidget):
    """
    Shows how the -LoG response of the candidates is distributed, and the threshold that keeps some of them.

    The line can be dragged. The widget only announces where the user released it: the threshold
    itself belongs to the blob detection inspector.

    Signals:
        threshold_changed_by_user: Emitted with the position of the line when the user releases it.
    """

    threshold_changed_by_user = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._values: NDArray[np.float32] = np.empty(0, dtype=np.float32)
        self._threshold = BlobParams.LOG_THRESHOLD_MIN
        self._moved_by_code = False  # True while the code, not the user, moves the line

        self.setBackground(None)
        self.setMenuEnabled(True)
        self.hideButtons()
        self.setLimits(yMin=0, xMin=0)
        self.setMinimumHeight(160)

        self.setLabel("left", texts.SEED_HISTOGRAM_LEFT_AXIS_LABEL)
        self.setLabel("bottom", texts.SEED_HISTOGRAM_BOTTOM_AXIS_LABEL)
        self.getAxis("bottom").enableAutoSIPrefix(False)

        # a single flat bar until there is data: BarGraphItem does not like empty
        self._bars = pg.BarGraphItem(x=np.zeros(1), height=np.zeros(1), width=1.0)
        self._bars.setVisible(False)
        self.addItem(self._bars)

        self._lo_g_threshold_line = pg.InfiniteLine(
            pos=self._threshold,
            angle=90,
            movable=True,
            bounds=(BlobParams.LOG_THRESHOLD_MIN, BlobParams.LOG_THRESHOLD_MAX),
            label="{value:0.2f}",
            labelOpts={"position": 0.9},
        )
        self.addItem(self._lo_g_threshold_line)
        self._lo_g_threshold_line.sigPositionChanged.connect(self._on_threshold_moved)
        self._lo_g_threshold_line.sigPositionChangeFinished.connect(self._on_threshold_released)

        self._update_range()
        self._update_title()

    @property
    def threshold(self) -> float:
        """Where the line is."""
        return self._threshold

    @property
    def seeds_response(self) -> NDArray[np.float32]:
        """The responses shown."""
        return self._values

    def set_seeds_response(self, values: NDArray | None) -> None:
        """
        Show the response of the candidates of a detection.

        Args:
            values: One LoG response per candidate, or None to empty the histogram.
        """

        self._values = (
            np.empty(0, dtype=np.float32) if values is None else np.asarray(values, dtype=np.float32).ravel()
        )
        self._redraw_bars()
        self._update_range()
        self._update_title()

    def set_threshold(self, value: float) -> None:
        """
        Move the line to `value`. It does not emit `threshold_changed_by_user`.

        Args:
            value: Threshold to show.
        """

        self._threshold = value
        self._moved_by_code = True

        try:
            self._lo_g_threshold_line.setValue(value)
        finally:
            self._moved_by_code = False

        self._update_range()
        self._update_title()

    def apply_theme(self, colors: ThemeColors) -> None:
        """Update background, axes, bars and threshold line colors."""

        self.setBackground(colors.raised_base)

        axis_pen = pg.mkPen(color=colors.text, width=1)
        text_pen = pg.mkPen(color=colors.text)

        bottom_axis = self.getAxis("bottom")
        bottom_axis.setPen(axis_pen)
        bottom_axis.setTextPen(text_pen)

        left_axis = self.getAxis("left")
        left_axis.setPen(axis_pen)
        left_axis.setTextPen(text_pen)

        bar_pen = pg.mkPen(colors.highlight, width=1.5)
        brush_color = QColor(colors.highlight)
        brush_color.setAlpha(90)
        bar_brush = pg.mkBrush(brush_color)
        self._bars.setOpts(pen=bar_pen, brush=bar_brush)

        self._lo_g_threshold_line.setPen(
            pg.mkPen(color=colors.highest_bound_hist, width=2, style=Qt.PenStyle.DashLine)
        )
        self._lo_g_threshold_line.setHoverPen(pg.mkPen(color=colors.highest_bound_hist, width=4))

        self.setTitle("", color=colors.text, size="9pt")

    def _redraw_bars(self) -> None:
        if self._values.size == 0:
            self._bars.setVisible(False)
            return

        bins = ceil(np.log2(len(self._values)) + 1)  # Sturges rule
        counts, edges = np.histogram(self._values, bins=bins)
        width = float(edges[1] - edges[0])
        self._bars.setOpts(x=edges[:-1] + width / 2, height=counts, width=width)
        self._bars.setVisible(True)

    def _update_range(self) -> None:
        # the threshold line is not part of the autorange, this set the range so that it is always visible
        top = max(float(self._values.max()) if self._values.size else 0.0, self._threshold)
        self.getViewBox().setXRange(BlobParams.LOG_THRESHOLD_MIN, max(top, 0.1), padding=0.1)
        self.enableAutoRange(axis="y")

    def _update_title(self, threshold: float | None = None) -> None:
        if self._values.size == 0:
            self.setTitle(texts.SEED_HISTOGRAM_EMPTY)
            return

        value = self._threshold if threshold is None else threshold
        count = int(np.count_nonzero(self._values > value))
        self.setTitle(texts.SEED_HISTOGRAM_TITLE.format(count=count))

    def _on_threshold_moved(self, line: pg.InfiniteLine) -> None:
        if not self._moved_by_code:
            self._update_title(float(line.value()))  # while dragging: how many candidates this would keep

    def _on_threshold_released(self, line: pg.InfiniteLine) -> None:
        if not self._moved_by_code:
            self.threshold_changed_by_user.emit(float(line.value()))

    @override
    def mouseDoubleClickEvent(self, event) -> None:
        self._update_range()
        super().mouseDoubleClickEvent(event)
