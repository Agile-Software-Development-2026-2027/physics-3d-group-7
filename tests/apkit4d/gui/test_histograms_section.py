from apkit4d.gui.constants import names
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.panels.histograms_section import HistogramsSection
from apkit4d.gui.views.widgets.preprocessed_intensity_histogram import PreprocessedIntensityHistogram
from apkit4d.gui.views.widgets.roi_intensity_histogram import RoiIntensityHistogram


def test_histograms_section_contains_both_histograms(qtbot) -> None:
    section = HistogramsSection()
    qtbot.addWidget(section)

    roi_hist = section.findChild(RoiIntensityHistogram, names.ROI_HISTOGRAM)
    preproc_hist = section.findChild(PreprocessedIntensityHistogram, names.PREPROC_HISTOGRAM)

    assert roi_hist is not None
    assert preproc_hist is not None
    assert section._histograms[0] is roi_hist
    assert section._histograms[1] is preproc_hist


def test_histograms_section_propagates_theme_and_expansion(qtbot) -> None:
    section = HistogramsSection()
    qtbot.addWidget(section)

    section.apply_theme(DARK_COLORS)
    assert section._roi_histogram.backgroundBrush().color().name().lower() == DARK_COLORS.raised_base.lower()
    assert (
        section._preproc_histogram.backgroundBrush().color().name().lower() == DARK_COLORS.raised_base.lower()
    )

    section.apply_theme(LIGHT_COLORS)
    assert section._roi_histogram.backgroundBrush().color().name().lower() == LIGHT_COLORS.raised_base.lower()
    assert (
        section._preproc_histogram.backgroundBrush().color().name().lower()
        == LIGHT_COLORS.raised_base.lower()
    )

    section.set_expanded(True, animate=False)
    assert section._roi_histogram._is_expanded is True
    assert section._preproc_histogram._is_expanded is True
