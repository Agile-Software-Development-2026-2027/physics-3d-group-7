"""
Unit tests for RightPanel and its theme and layout synchronization.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy

from apkit4d.gui.constants import names
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.right_panel import BottomStatsSection, RightPanel


def test_right_panel_init(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    assert panel.objectName() == names.RIGHT_PANEL
    assert panel.theme == Theme.DARK
    assert len(panel.sections) == 9
    assert panel.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert panel.scroll_area.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert panel.scroll_area.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding

    # Verify top bar and bottom stats presence
    assert panel.top_bar is not None
    assert panel.toggle_all_btn.text() == "Toggle All"
    assert panel.bottom_stats is not None
    assert not panel.bottom_stats.is_expanded()
    assert panel.bottom_stats.summary_label.text() == "Working: 15%"


def test_right_panel_theme_switch(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    panel.set_theme(Theme.LIGHT)
    assert panel.theme == Theme.LIGHT
    assert LIGHT_COLORS.button in panel.sections[0].toggle_button.styleSheet()
    assert LIGHT_COLORS.placeholder_text in panel.scroll_area.styleSheet()
    assert LIGHT_COLORS.button in panel.top_bar.styleSheet()
    assert LIGHT_COLORS.window in panel.bottom_stats.styleSheet()

    panel.set_theme(Theme.DARK)
    assert panel.theme == Theme.DARK
    assert DARK_COLORS.button in panel.sections[0].toggle_button.styleSheet()
    assert DARK_COLORS.placeholder_text in panel.scroll_area.styleSheet()
    assert DARK_COLORS.button in panel.top_bar.styleSheet()
    assert DARK_COLORS.window in panel.bottom_stats.styleSheet()


def test_right_panel_toggle_and_expand_all(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    # Initial state: all collapsed
    assert all(not s.is_expanded() for s in panel.sections)

    # Toggle all -> should expand all
    panel.toggle_all()
    assert all(s.is_expanded() for s in panel.sections)

    # Toggle all again -> should collapse all
    panel.toggle_all()
    assert all(not s.is_expanded() for s in panel.sections)

    # Explicit expand_all and collapse_all
    panel.expand_all()
    assert all(s.is_expanded() for s in panel.sections)

    panel.collapse_all()
    assert all(not s.is_expanded() for s in panel.sections)


def test_bottom_stats_section_collapse_and_expand(qtbot) -> None:
    stats = BottomStatsSection()
    qtbot.addWidget(stats)

    assert not stats.is_expanded()
    assert stats._details_frame.maximumHeight() == 0
    assert stats._toggle_btn.text() == "▲"

    # Expand without animation for instant assert
    stats.set_expanded(True, animate=False)
    assert stats.is_expanded()
    assert stats._details_frame.maximumHeight() > 0
    assert stats._toggle_btn.text() == "▼"

    # Redundant set_expanded should return early
    stats.set_expanded(True, animate=False)
    assert stats.is_expanded()

    # Collapse with animation
    stats.toggle(animate=True)
    assert not stats.is_expanded()
    assert stats._toggle_btn.text() == "▲"

    # Text updates
    stats.set_summary("Progress: 50%")
    assert stats.summary_label.text() == "Progress: 50%"

    stats.set_details("All tasks completed.")
    assert stats.details_label.text() == "All tasks completed."


def test_right_panel_stats_helpers(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    panel.set_stats_summary("Computing 80%")
    assert panel.bottom_stats.summary_label.text() == "Computing 80%"

    panel.set_stats_details("Elapsed time: 10s")
    assert panel.bottom_stats.details_label.text() == "Elapsed time: 10s"

    panel.toggle_stats(animate=False)
    assert panel.bottom_stats.is_expanded()


def test_right_panel_add_and_remove_section(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    initial_count = len(panel.sections)
    new_section = AccordionSection("New Section")
    panel.add_section(new_section)

    assert len(panel.sections) == initial_count + 1
    assert panel.sections[-1] is new_section
    assert DARK_COLORS.button in new_section.toggle_button.styleSheet()

    panel.remove_section(new_section)
    assert len(panel.sections) == initial_count


def test_right_panel_clear_sections(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    panel.clear_sections()
    assert len(panel.sections) == 0


def test_right_panel_add_control(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    label = QLabel("Custom Control")
    panel.add_control(label)
    assert label.parent() is not None


def test_main_controller_syncs_right_panel_theme(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window)

    # Initial theme should match controller
    assert window.right_panel.theme == controller.theme_controller.theme

    # Toggle theme via left panel switch request
    window.left_panel.theme_switch_requested.emit()
    assert window.right_panel.theme == controller.theme_controller.theme
    assert window.right_panel.theme == Theme.LIGHT

    # Toggle back to dark
    window.left_panel.theme_switch_requested.emit()
    assert window.right_panel.theme == Theme.DARK
