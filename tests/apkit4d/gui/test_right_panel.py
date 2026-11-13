"""
Unit tests for RightPanel, BottomStatsSection, and its theme, layout, and control synchronization.
"""

from typing import assert_never

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDoubleSpinBox, QLabel, QSizePolicy, QSpinBox
from pytestqt.qtbot import QtBot

from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.right_panel import BottomStatsSection, RightPanel
from apkit4d.gui.views.widgets.blob_detection_inspector import BlobDetectionInspector
from tests.apkit4d.gui.helper import find_widget


def test_right_panel_init(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    assert panel.objectName() == names.RIGHT_PANEL
    assert panel.theme == Theme.DARK
    # 5 consolidated stages: roi, preprocessing, detection, tracking, batch
    assert len(panel.sections) == 5
    assert panel.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert panel.scroll_area.sizePolicy().verticalPolicy() == QSizePolicy.Policy.Expanding
    assert panel.scroll_area.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Expanding

    # Verify top bar and bottom stats presence
    assert panel.top_bar is not None
    assert panel.top_bar.objectName() == names.RIGHT_PANEL_TOP_BAR
    assert panel.toggle_all_btn.text() == texts.BUTTON_TOGGLE_ALL
    assert panel.toggle_all_btn.objectName() == names.TOGGLE_ALL_BUTTON

    assert panel.bottom_stats is not None
    assert not panel.bottom_stats.is_expanded()
    assert panel.bottom_stats.summary_label.text() == texts.STATS_DEFAULT_SUMMARY

    # Verify each section has plan up to this button and its inspector
    for step in PipelineStep:
        assert panel.get_section(step) is not None
        assert panel.get_section(step.value) is not None

        play_btn = panel.get_play_button(step)
        assert play_btn is not None
        assert play_btn.text() == texts.BUTTON_PLAY_STAGE
        assert play_btn.objectName() == names.PLAY_STAGE_BUTTON

        match step:
            case PipelineStep.ROI:
                # TODO: add test when the step is implemented
                pass
            case PipelineStep.PREPROCESSING:
                # TODO: add test when the step is implemented
                pass
            case PipelineStep.DETECTION:
                inspector = find_widget(panel, BlobDetectionInspector, names.DETECTION_INSPECTOR_STEP)
                assert inspector is not None
            case PipelineStep.TRACKING:
                # TODO: add test when the step is implemented
                pass
            case PipelineStep.BATCH:
                # TODO: add test when the step is implemented
                pass
            case _:
                assert_never(step)


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


def test_right_panel_step_status_update(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    roi_section = panel.get_section(PipelineStep.ROI)
    assert roi_section is not None
    assert roi_section.status == StepStatus.IDLE

    panel.set_step_status(PipelineStep.ROI, StepStatus.RUNNING)
    assert roi_section.status == StepStatus.RUNNING

    panel.set_step_status("roi", StepStatus.COMPLETED)
    assert roi_section.status == StepStatus.COMPLETED


def test_right_panel_param_changed_signal(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    # TODO: implement signal check when pipeline steps are implemented


def test_right_panel_plan_stage_signal(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    play_btn = panel.get_play_button(PipelineStep.DETECTION)
    assert play_btn is not None

    plan_requested_emitted: list[object] = []
    panel.plan_stage_requested.connect(plan_requested_emitted.append)

    with qtbot.waitSignal(panel.run_stage_requested) as blocker:
        play_btn.click()
    assert blocker.args == [PipelineStep.DETECTION]
    # Verify play click only emits run_stage_requested, not duplicate plan_stage_requested
    assert len(plan_requested_emitted) == 0


def test_right_panel_complete_stage_signal(qtbot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    # TODO: implement complete stage check when pipeline steps are implemented


def test_bottom_stats_section_collapse_and_expand(qtbot) -> None:
    stats = BottomStatsSection()
    qtbot.addWidget(stats)

    assert stats.objectName() == names.BOTTOM_STATS_SECTION
    assert not stats.is_expanded()
    assert stats._details_frame.maximumHeight() == 0
    assert stats._toggle_btn.text() == texts.STATS_ARROW_COLLAPSED

    # Expand without animation for instant assert
    stats.set_expanded(True, animate=False)
    assert stats.is_expanded()
    assert stats._details_frame.maximumHeight() > 0
    assert stats._toggle_btn.text() == texts.STATS_ARROW_EXPANDED

    # Redundant set_expanded should return early
    stats.set_expanded(True, animate=False)
    assert stats.is_expanded()

    # Collapse with animation
    stats.toggle(animate=True)
    assert not stats.is_expanded()
    assert stats._toggle_btn.text() == texts.STATS_ARROW_COLLAPSED

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


def test_main_controller_initialization_and_theme_sync(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window)

    # Initial theme should match controller
    assert window.right_panel.theme == controller.theme_controller.theme
    assert controller.pipeline_model is not None
    assert controller.pipeline_controller is not None
    assert controller.pipeline_controller.model is controller.pipeline_model
    assert controller.pipeline_controller.view is window.right_panel

    # Toggle theme via left panel switch request
    window.left_panel.theme_switch_requested.emit()
    assert window.right_panel.theme == controller.theme_controller.theme
    assert window.right_panel.theme == Theme.LIGHT

    # Toggle back to dark
    window.left_panel.theme_switch_requested.emit()
    assert window.right_panel.theme == Theme.DARK


def test_right_panel_tracking_param_changed_signal(qtbot: QtBot) -> None:
    panel = RightPanel()
    qtbot.addWidget(panel)

    min_len = panel.findChild(QSpinBox, names.TRACKING_INSPECTOR_MIN_LEN)
    max_gap = panel.findChild(QSpinBox, names.TRACKING_INSPECTOR_MAX_GAP)
    max_speed = panel.findChild(QDoubleSpinBox, names.TRACKING_INSPECTOR_MAX_SPEED)

    assert min_len is not None
    assert max_gap is not None
    assert max_speed is not None

    with qtbot.waitSignal(panel.step_param_changed) as blocker:
        min_len.setValue(6)
    assert blocker.args == ["tracking", "min_len", 6]

    with qtbot.waitSignal(panel.step_param_changed) as blocker:
        max_gap.setValue(4)
    assert blocker.args == ["tracking", "max_gap", 4]

    with qtbot.waitSignal(panel.step_param_changed) as blocker:
        max_speed.setValue(300.0)
    assert blocker.args == ["tracking", "max_speed_um_s", 300.0]
