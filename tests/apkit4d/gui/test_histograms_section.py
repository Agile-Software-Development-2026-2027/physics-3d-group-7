"""
Unit tests for HistogramsSection.
"""

import pytest
from PySide6.QtWidgets import QLabel

from apkit4d.gui.constants import names, texts
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS
from apkit4d.gui.views.panels.histograms_section import HistogramsSection
from apkit4d.gui.views.widgets.roi_intensity_histogram import RoiIntensityHistogram
from apkit4d.gui.views.widgets.seed_response_histogram import SeedResponseHistogram


def test_histograms_section_init(qtbot) -> None:
    section = HistogramsSection()
    qtbot.addWidget(section)

    assert section.objectName() == names.HISTOGRAMS_SECTION
    assert texts.SECTION_HISTOGRAMS in section.title
    assert section._roi_histogram is not None
    assert section._histogram_2 is None
    assert section.seed_response_histogram is not None


def test_histograms_section_set_histogram(qtbot) -> None:
    section = HistogramsSection()
    qtbot.addWidget(section)

    label2 = QLabel("Histogram 2")

    section.set_histogram(1, label2)
    assert section._histogram_2 is label2

    new_hist_3 = SeedResponseHistogram()
    section.set_histogram(2, new_hist_3)
    assert section.seed_response_histogram is new_hist_3

    new_hist1 = RoiIntensityHistogram()
    section.set_histogram(0, new_hist1)
    assert section._roi_histogram is new_hist1

    with pytest.raises(IndexError):
        section.set_histogram(3, QLabel("Invalid"))


def test_histograms_section_apply_theme(qtbot) -> None:
    section = HistogramsSection()
    qtbot.addWidget(section)

    section.apply_theme(DARK_COLORS)
    assert section._roi_histogram.lowest_line.pen.color().name().lower() == "#e5c07b"
    assert section.seed_response_histogram._lo_g_threshold_line.pen.color().name().lower() == "#e06c75"

    section.apply_theme(LIGHT_COLORS)
    assert section._roi_histogram.lowest_line.pen.color().name().lower() == "#b45309"
    assert section.seed_response_histogram._lo_g_threshold_line.pen.color().name().lower() == "#dc2626"
