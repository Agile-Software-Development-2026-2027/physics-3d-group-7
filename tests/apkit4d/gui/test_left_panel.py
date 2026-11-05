"""
Unit tests for LeftPanel.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton

from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.left_panel import LeftPanel


@pytest.fixture
def panel(qtbot) -> LeftPanel:
    left_panel = LeftPanel()
    qtbot.addWidget(left_panel)
    return left_panel


def test_left_panel_has_the_two_sections(panel) -> None:
    assert panel.objectName() == names.LEFT_PANEL
    assert panel.findChild(AccordionSection, names.APPEARANCE_SECTION) is panel.appearance_section
    assert panel.findChild(AccordionSection, names.LAYERS_SECTION) is panel.layers_section
    assert panel.appearance_section.title == texts.SECTION_APPEARANCE
    assert panel.layers_section.title == texts.SECTION_LAYERS


def test_only_the_appearance_section_starts_open(panel) -> None:
    assert panel.appearance_section.is_expanded()
    assert not panel.layers_section.is_expanded()


def test_open_section_is_tall_enough_for_its_content(panel) -> None:
    content = panel.appearance_section.content_area
    assert content.maximumHeight() >= content.sizeHint().height()


def test_theme_button_asks_to_switch_the_theme(panel, qtbot) -> None:
    button = panel.findChild(QPushButton, names.THEME_BUTTON)
    with qtbot.waitSignal(panel.theme_switch_requested, timeout=1000):
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)


def test_set_theme_paints_the_sections(panel) -> None:
    panel.set_theme(Theme.LIGHT)
    assert LIGHT_COLORS.button in panel.appearance_section.toggle_button.styleSheet()
    assert LIGHT_COLORS.button in panel.layers_section.toggle_button.styleSheet()

    panel.set_theme(Theme.DARK)
    assert DARK_COLORS.button in panel.appearance_section.toggle_button.styleSheet()
    assert DARK_COLORS.button in panel.layers_section.toggle_button.styleSheet()


def test_main_controller_keeps_the_left_panel_on_the_active_theme(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    MainController(window, qapp, window)
    toggle_button = window.left_panel.appearance_section.toggle_button
    assert DARK_COLORS.button in toggle_button.styleSheet()

    window.findChild(QPushButton, names.THEME_BUTTON).click()
    assert LIGHT_COLORS.button in toggle_button.styleSheet()
