"""
Unit tests for PipelineController orchestrating PipelineModel and RightPanel.
"""

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.models.pipeline_model import (
    PIPELINE_STEP_ORDER,
    PipelineModel,
    PipelineStep,
    StepStatus,
)
from apkit4d.gui.views.panels.right_panel import RightPanel


def test_pipeline_controller_init(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    assert controller.model is model
    assert controller.view is view
    assert controller.target_step is None

    # Synchronized initial states
    for step in PIPELINE_STEP_ORDER:
        sec = view.get_section(step)
        assert sec is not None
        assert sec.status == StepStatus.IDLE


def test_pipeline_controller_interactive_workflow(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Click "Plan up to this" on Detection (step 3)
    plan_detection_btn = view.get_plan_button(PipelineStep.DETECTION)
    assert plan_detection_btn is not None
    plan_detection_btn.click()

    assert controller.target_step == PipelineStep.DETECTION
    assert model.get_status(PipelineStep.ROI) == StepStatus.PENDING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.BATCH) == StepStatus.IDLE
    # No action event text like "Planned up to Detection"; displays state of work
    assert view.bottom_stats.summary_label.text() == texts.STATS_DEFAULT_SUMMARY

    # Attempt to "Complete this" on Detection before ROI/Preprocessing: ignored without error
    complete_detection_btn = view.get_complete_button(PipelineStep.DETECTION)
    assert complete_detection_btn is not None
    complete_detection_btn.click()

    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    # Still shows state of work (not an error message)
    assert view.bottom_stats.summary_label.text() == texts.STATS_DEFAULT_SUMMARY

    # Click "Complete this" on ROI
    complete_roi_btn = view.get_complete_button(PipelineStep.ROI)
    assert complete_roi_btn is not None
    complete_roi_btn.click()

    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    # Preprocessing was PENDING, so it advances to RUNNING!
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    # Bottom stats reflects active execution in progress
    assert "Working: Preprocessing..." in view.bottom_stats.summary_label.text()
    assert "Active Step: Preprocessing" in view.bottom_stats.details_label.text()
    assert "Completed: ROI" in view.bottom_stats.details_label.text()

    # Click "Complete this" on Preprocessing
    complete_prep_btn = view.get_complete_button(PipelineStep.PREPROCESSING)
    assert complete_prep_btn is not None
    complete_prep_btn.click()

    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.COMPLETED
    # Detection was PENDING, so it advances to RUNNING!
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.RUNNING
    assert "Working: Detection..." in view.bottom_stats.summary_label.text()
    assert "Completed: ROI, Preprocessing" in view.bottom_stats.details_label.text()

    # Click "Complete this" on Detection
    complete_detection_btn.click()
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.BATCH) == StepStatus.IDLE
    # Idle now: shows completed progress count and completed stages list
    assert "Completed: 3 / 5 stages" in view.bottom_stats.summary_label.text()
    assert "ROI, Preprocessing, Detection" in view.bottom_stats.details_label.text()

    # Test parameter change cascading invalidation:
    # User edits number field on ROI
    roi_num_field = view.get_number_field(PipelineStep.ROI)
    assert roi_num_field is not None
    roi_num_field.setValue(99)

    # ROI becomes IDLE, and downstream Preprocessing and Detection cascade to IDLE!
    assert model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE
    # Stats automatically reflects updated state (0 completed, idle) without event logging
    assert view.bottom_stats.summary_label.text() == texts.STATS_DEFAULT_SUMMARY


def test_pipeline_controller_run_pipeline_full(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Run full pipeline programmatically
    controller.run_pipeline()
    assert controller.target_step == PipelineStep.BATCH
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING

    for step in PIPELINE_STEP_ORDER[1:]:
        assert model.get_status(step) == StepStatus.PENDING

    for step in PIPELINE_STEP_ORDER:
        controller.complete_step(step)

    assert model.is_complete
    assert view.bottom_stats.summary_label.text() == texts.STATS_COMPLETED_SUMMARY


def test_pipeline_controller_reset_pipeline(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    controller.run_pipeline()
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING

    controller.reset_pipeline()
    assert controller.target_step is None
    for step in PIPELINE_STEP_ORDER:
        assert model.get_status(step) == StepStatus.IDLE
        sec = view.get_section(step)
        assert sec is not None
        assert sec.status == StepStatus.IDLE

    assert view.bottom_stats.summary_label.text() == texts.STATS_DEFAULT_SUMMARY
