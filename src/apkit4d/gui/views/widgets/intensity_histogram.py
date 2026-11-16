from typing import override

import numpy as np
import pyqtgraph as pg
from numpy.typing import NDArray
from PySide6.QtCore import Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget

from apkit4d.gui.constants import texts
from apkit4d.gui.theme import DEFAULT_THEME, THEME_COLORS, ThemeColors


class IntensityHistogram(pg.PlotWidget):
    """Base PyQtGraph histogram widget with log-Y scale, theme support, and collapse deferral."""

    NUM_BINS: int
    recompute_requested = Signal(bool)  # reset_range

    def __init__(self, object_name: str, x_units: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent=parent)
        self.setObjectName(object_name)
        self.setMinimumHeight(230)
        self.setMaximumHeight(280)

        self._volume: NDArray | None = None
        self._current_title: str = ""
        self._theme_colors: ThemeColors = THEME_COLORS[DEFAULT_THEME]

        self._is_expanded: bool = False
        self._dirty: bool = False
        self._pending_reset_range: bool = False
        self._async_mode: bool = False

        plot_item = self.getPlotItem()
        plot_item.hideButtons()
        plot_item.setMenuEnabled(True)
        self.setLogMode(x=False, y=True)
        self.setLabel("bottom", texts.LABEL_HISTOGRAM_INTENSITY, units=x_units)
        self.setLabel("left", texts.LABEL_HISTOGRAM_COUNTS)

        bins = np.linspace(0.0, 1.0, self.NUM_BINS + 1)
        counts = np.zeros(self.NUM_BINS, dtype=float)
        self._curve_item = self.plot(bins, counts, stepMode="center", fillLevel=0)

    @property
    def volume(self) -> NDArray | None:
        return self._volume

    @property
    def title_text(self) -> str:
        return self._current_title

    def set_async_mode(self, enabled: bool) -> None:
        """When True, delegates recomputation to an external controller via `recompute_requested`."""
        self._async_mode = enabled

    def set_volume(self, volume: NDArray | None) -> None:
        self._volume = volume
        self._dirty = True
        self._pending_reset_range = True
        if self._is_expanded:
            self._trigger_recompute(reset_range=True)

    def _trigger_recompute(self, reset_range: bool = False) -> None:
        if self._async_mode:
            self.recompute_requested.emit(reset_range)
        else:
            self._recompute_histogram(reset_range=reset_range)

    def _recompute_histogram(self, reset_range: bool = False) -> None:
        raise NotImplementedError

    def _render_title(self) -> None:
        raise NotImplementedError

    def apply_theme(self, colors: ThemeColors) -> None:
        self._theme_colors = colors
        self.setBackground(colors.raised_base)

        axis_pen = pg.mkPen(color=colors.text, width=1)
        text_pen = pg.mkPen(color=colors.text)

        for axis_name in ("bottom", "left"):
            axis = self.getAxis(axis_name)
            axis.setPen(axis_pen)
            axis.setTextPen(text_pen)

        curve_pen = pg.mkPen(color=colors.highlight, width=1.5)
        c = QColor(colors.highlight)
        c.setAlpha(90)
        self._curve_item.setPen(curve_pen)
        self._curve_item.setBrush(pg.mkBrush(c))
        self._render_title()

    @override
    def mouseDoubleClickEvent(self, event) -> None:
        self.reset_zoom()
        super().mouseDoubleClickEvent(event)

    def reset_zoom(self) -> None:
        self.getViewBox().setXRange(0.0, self._x_max(), padding=None)
        self.enableAutoRange(axis="y")

    def _x_max(self) -> float:
        return 1.0

    def set_expanded(self, expanded: bool) -> None:
        if self._is_expanded == expanded:
            return
        self._is_expanded = expanded
        if expanded and self._dirty:
            self._trigger_recompute(reset_range=self._pending_reset_range)

    @property
    def is_expanded(self) -> bool:
        return self._is_expanded

    @property
    def pending_reset_range(self) -> bool:
        return self._pending_reset_range
