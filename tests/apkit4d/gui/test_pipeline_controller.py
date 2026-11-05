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


def test_pipeline_controller_run_up_to_intermediate_stage(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Click Execute button on Blob Detection (step 3)
    detection_btn = view.get_execute_button(PipelineStep.DETECTION)
    assert detection_btn is not None
    detection_btn.click()

    assert controller.target_step == PipelineStep.DETECTION
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    # Downstream steps remain IDLE!
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.BATCH) == StepStatus.IDLE

    # Complete ROI -> advances to Preprocessing
    controller.complete_step(PipelineStep.ROI)
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.RUNNING

    # Complete Preprocessing -> advances to Detection
    controller.complete_step(PipelineStep.PREPROCESSING)
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.RUNNING

    # Complete Detection -> reached target, stops!
    controller.complete_step(PipelineStep.DETECTION)
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED
    assert controller.target_step is None
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.BATCH) == StepStatus.IDLE
    assert "Completed up to Detection" in view.bottom_stats.summary_label.text()

    # Clicking Execute again on Detection reports already completed
    detection_btn.click()
    assert "Stage 'Detection' is already completed." in view.bottom_stats.details_label.text()


def test_pipeline_controller_run_pipeline_full(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Run full pipeline
    controller.run_pipeline()
    assert controller.target_step == PipelineStep.BATCH
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING

    for step in PIPELINE_STEP_ORDER[1:]:
        assert model.get_status(step) == StepStatus.PENDING

    for step in PIPELINE_STEP_ORDER:
        controller.complete_step(step)

    assert model.is_complete
    assert view.bottom_stats.summary_label.text() == texts.STATS_COMPLETED_SUMMARY
    assert texts.STATS_COMPLETED_DETAILS in view.bottom_stats.details_label.text()


def test_pipeline_controller_run_single_step(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Run single step ROI
    controller.run_step("roi")
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING

    # Attempting invalid step name
    controller.run_step("non_existent_step")


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


def test_pipeline_controller_view_param_change_handling(qtbot) -> None:
    view = RightPanel()
    qtbot.addWidget(view)
    model = PipelineModel()
    controller = PipelineController(model, view)

    # Complete ROI
    controller.run_pipeline()
    controller.complete_step(PipelineStep.ROI)
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED

    # User alters parameter in ROI from view
    view.step_param_changed.emit("roi", "z_start", 12)
    assert model.get_step_params(PipelineStep.ROI) == {"z_start": 12}
    # Invalidation resets ROI and downstream steps to IDLE
    assert model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE

    # Invalid step name emission handled safely
    view.step_param_changed.emit("unknown_step", "param", 1)
