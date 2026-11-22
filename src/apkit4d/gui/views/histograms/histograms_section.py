"""Histograms accordion section in the left panel."""

from typing import Protocol, runtime_checkable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QWidget

from apkit4d.gui.constants import names, texts
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, ThemeColors
from apkit4d.gui.views.histograms.preprocessed_intensity_histogram import PreprocessedIntensityHistogram
from apkit4d.gui.views.histograms.roi_intensity_histogram import RoiIntensityHistogram
from apkit4d.gui.views.histograms.seed_response_histogram import SeedResponseHistogram
from apkit4d.gui.views.widgets.accordion import AccordionSection

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

        self.seed_response_histogram = SeedResponseHistogram(self)
        self.seed_response_histogram.setObjectName(names.SEED_RESPONSE_HISTOGRAM)
        self.add_widget(self.seed_response_histogram)
        self._histograms[2] = self.seed_response_histogram

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
