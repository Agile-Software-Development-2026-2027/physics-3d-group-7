"""
Unit tests for PipelineController orchestrating PipelineModel and RightPanel.
"""

import pytest

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

    # Click play on Detection (step 3): plans up to Detection and starts processing from top (ROI)
    play_detection_btn = view.get_play_button(PipelineStep.DETECTION)
    assert play_detection_btn is not None
    play_detection_btn.click()

    assert controller.target_step == PipelineStep.DETECTION
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.BATCH) == StepStatus.IDLE
    assert "Working: ROI..." in view.bottom_stats.summary_label.text()

    # Attempt to "Complete this" on Detection before ROI/Preprocessing: raises ValueError
    complete_detection_btn = view.get_complete_button(PipelineStep.DETECTION)
    assert complete_detection_btn is not None
    with qtbot.capture_exceptions() as exceptions:
        complete_detection_btn.click()
    assert len(exceptions) == 1
    assert exceptions[0][0] is ValueError
    assert "prior step 'roi' is not completed" in str(exceptions[0][1])

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

    # Test parameter change behavior:
    # User edits number field on ROI: completed states are NOT immediately invalidated!
    roi_num_field = view.get_number_field(PipelineStep.ROI)
    assert roi_num_field is not None
    roi_num_field.setValue(99)

    # ROI, Preprocessing, Detection all remain COMPLETED (hours of processing are safe)
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED
    assert "Completed: 3 / 5 stages" in view.bottom_stats.summary_label.text()

    # When ROI is planned/run again with modified parameter:
    # ROI was completed but value changed -> assumed reworked, so downstream stages invalidate!
    play_detection_btn.click()
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING


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


def test_pipeline_controller_run_up_to_while_step_already_running(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Start execution up to Preprocessing
    controller.run_up_to(PipelineStep.PREPROCESSING)
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING

    # Complete ROI -> Preprocessing transitions to RUNNING
    controller.complete_step(PipelineStep.ROI)
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.RUNNING
    assert model.current_running_step == PipelineStep.PREPROCESSING

    # Verify plan_up_to returns the correct sequence of steps [PREPROCESSING, DETECTION, TRACKING, BATCH]
    planned = controller.plan_up_to(PipelineStep.BATCH)
    assert planned == [
        PipelineStep.PREPROCESSING,
        PipelineStep.DETECTION,
        PipelineStep.TRACKING,
        PipelineStep.BATCH,
    ]

    # User clicks execute on Batch Export while Preprocessing is RUNNING.
    # Because planned[0] is PREPROCESSING (which is already RUNNING), it doesn't mistakenly
    # attempt to run DETECTION or throw a ValueError.
    play_batch_btn = view.get_play_button(PipelineStep.BATCH)
    assert play_batch_btn is not None
    play_batch_btn.click()

    assert controller.target_step == PipelineStep.BATCH
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.PENDING
    assert model.get_status(PipelineStep.BATCH) == StepStatus.PENDING

    # 4. As Preprocessing completes, execution advances sequentially without errors
    controller.complete_step(PipelineStep.PREPROCESSING)
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.RUNNING

    controller.complete_step(PipelineStep.DETECTION)
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.RUNNING

    controller.complete_step(PipelineStep.TRACKING)
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.BATCH) == StepStatus.RUNNING

    controller.complete_step(PipelineStep.BATCH)
    assert model.get_status(PipelineStep.BATCH) == StepStatus.COMPLETED
    assert model.is_complete


def test_pipeline_controller_complete_stage_raises_value_error_when_prior_incomplete() -> None:
    view = RightPanel()
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Attempting to complete Preprocessing when ROI is not completed raises ValueError
    with pytest.raises(
        ValueError, match="Cannot set 'preprocessing' to completed: prior step 'roi' is not completed."
    ):
        controller.complete_stage(PipelineStep.PREPROCESSING)

    # Attempting to complete Detection when Preprocessing is not completed raises ValueError
    with pytest.raises(
        ValueError, match="Cannot set 'detection' to completed: prior step 'roi' is not completed."
    ):
        controller.complete_stage(PipelineStep.DETECTION)
