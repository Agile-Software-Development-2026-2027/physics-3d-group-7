"""Histograms accordion section in the left panel."""

from typing import Protocol, runtime_checkable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from apkit4d.gui.constants import names, texts
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, ThemeColors
from apkit4d.gui.views.widgets.preprocessed_intensity_histogram import PreprocessedIntensityHistogram
from apkit4d.gui.views.widgets.roi_intensity_histogram import RoiIntensityHistogram

__all__ = ["CollapsibleHistogram", "HistogramsSection", "ThemeableHistogram"]


@runtime_checkable
class ThemeableHistogram(Protocol):
    """Protocol for histogram widgets that support theme updates."""

    def apply_theme(self, colors: ThemeColors) -> None: ...


@runtime_checkable
class CollapsibleHistogram(Protocol):
    """Protocol for histogram widgets that pause recomputation when collapsed."""

    def set_expanded(self, expanded: bool) -> None: ...


class HistogramsSection(AccordionSection):
    """
    Accordion section hosting up to 3 histograms in the left sidebar.

    For now hosts the first interactive histogram (ROI voxel intensity distribution)
    and maintains slots and layout ready for the remaining two histograms.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(texts.SECTION_HISTOGRAMS, parent=parent)
        self.setObjectName(names.HISTOGRAMS_SECTION)

        self._histograms: list[QWidget | None] = [None, None, None]

        self._roi_histogram: RoiIntensityHistogram = RoiIntensityHistogram(self)
        self._roi_histogram.setObjectName(names.ROI_HISTOGRAM)
        self._roi_histogram.set_expanded(self.is_expanded())
        self.add_widget(self._roi_histogram)
        self._histograms[0] = self._roi_histogram

        self._preproc_histogram: PreprocessedIntensityHistogram = PreprocessedIntensityHistogram(self)
        self._preproc_histogram.setObjectName(names.PREPROC_HISTOGRAM)
        self._preproc_histogram.set_expanded(self.is_expanded())
        self.add_widget(self._preproc_histogram)
        self._histograms[1] = self._preproc_histogram

        # TODO: add the third histograms
        self._histogram_3: QWidget | None = None

        self.expanded_changed.connect(self._on_expanded_changed)

        tip = QLabel(texts.HISTOGRAMS_TIP, wordWrap=True)
        tip.setContentsMargins(0, 8, 0, 0)
        tip.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft)
        tip.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        font = tip.font()
        font.setPointSize(8)
        tip.setFont(font)
        self.add_widget(tip)

        self.apply_theme(THEME_COLORS[DEFAULT_THEME])

    def set_histogram(self, index: int, widget: QWidget) -> None:
        """
        Set or replace one of the 3 histogram slots (index 0, 1, or 2).

        Args:
            index: Slot index (0, 1, or 2).
            widget: Histogram widget to install.
        """

        if index < 0 or index > 2:
            raise IndexError("Histogram index must be 0, 1, or 2.")

        existing = self._histograms[index]
        if existing is not None:
            self.content_layout.removeWidget(existing)
            existing.setParent(None)

        self._histograms[index] = widget
        if index == 0 and isinstance(widget, RoiIntensityHistogram):
            self._roi_histogram = widget
        elif index == 1 and isinstance(widget, PreprocessedIntensityHistogram):
            self._preproc_histogram = widget
        elif index == 2:
            self._histogram_3 = widget

        if isinstance(widget, CollapsibleHistogram):
            widget.set_expanded(self.is_expanded())

        self.add_widget(widget)

    def apply_theme(self, colors: ThemeColors) -> None:
        """
        Apply theme colors to header, content area, and contained histograms.

        Args:
            colors: Colors of the active theme.
        """

        super().apply_theme(colors)
        for hist in getattr(self, "_histograms", ()):  # gets called before __init__
            if isinstance(hist, ThemeableHistogram):
                hist.apply_theme(colors)

    def _on_expanded_changed(self, expanded: bool) -> None:
        for hist in self._histograms:
            if isinstance(hist, CollapsibleHistogram):
                hist.set_expanded(expanded)
