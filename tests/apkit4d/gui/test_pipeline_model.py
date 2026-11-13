"""
Unit tests for PipelineModel verifying state transitions, dependencies, and cascading invalidation.
"""

import pytest

from apkit4d.gui.models.pipeline_model import (
    PIPELINE_STEP_ORDER,
    PipelineModel,
    PipelineStep,
    StepStatus,
)
from apkit4d.preprocessing import BgMode, PreprocParams


def test_pipeline_model_init(qtbot) -> None:
    model = PipelineModel()
    assert model.step_order == PIPELINE_STEP_ORDER
    assert len(model.statuses) == len(PIPELINE_STEP_ORDER)
    assert all(status == StepStatus.IDLE for status in model.statuses.values())
    assert not model.is_complete
    assert model.active_step is None


def test_pipeline_model_can_run_step() -> None:
    model = PipelineModel()

    # First step (ROI) has no prerequisites and is not running
    assert model.can_run_step(PipelineStep.ROI)
    # Subsequent steps cannot run yet
    assert not model.can_run_step(PipelineStep.PREPROCESSING)
    assert not model.can_run_step(PipelineStep.DETECTION)

    # If ROI is running, can_run_step is False (already running)
    model.set_step_status(PipelineStep.ROI, StepStatus.RUNNING)
    assert not model.can_run_step(PipelineStep.ROI)
    assert not model.can_run_step(PipelineStep.PREPROCESSING)

    # Complete ROI
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    assert model.can_run_step(PipelineStep.PREPROCESSING)
    assert not model.can_run_step(PipelineStep.DETECTION)


def test_pipeline_model_sequential_progression(qtbot) -> None:
    model = PipelineModel()

    # Track status changed signals
    status_signals: list[tuple[PipelineStep, StepStatus]] = []
    model.step_status_changed.connect(lambda step, st: status_signals.append((step, st)))

    model.set_step_status(PipelineStep.ROI, StepStatus.RUNNING)
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert model.active_step == PipelineStep.ROI

    # Setting same status again is a no-op
    model.set_step_status(PipelineStep.ROI, StepStatus.RUNNING)
    assert len(status_signals) == 1

    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.active_step is None


def test_pipeline_model_dependency_invariants() -> None:
    model = PipelineModel()

    # Cannot set a later step to COMPLETED or RUNNING before prior steps complete
    with pytest.raises(ValueError, match="prior step 'roi' is not completed"):
        model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)

    with pytest.raises(ValueError, match="prior step 'roi' is not completed"):
        model.set_step_status(PipelineStep.DETECTION, StepStatus.RUNNING)


def test_pipeline_model_cascading_invalidation_on_status_change() -> None:
    model = PipelineModel()

    # Complete ROI and Preprocessing
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)
    model.set_step_status(PipelineStep.DETECTION, StepStatus.RUNNING)

    # If Preprocessing status changes back to IDLE, Detection must be invalidated to IDLE
    model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.IDLE)
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE

    # If ROI changes back to IDLE, subsequent completed/pending steps are reset to IDLE
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)
    model.set_step_status(PipelineStep.ROI, StepStatus.IDLE)
    assert model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE


def test_pipeline_model_update_step_params_cascading() -> None:
    model = PipelineModel()

    # Complete ROI and Preprocessing
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)

    # Update parameters on ROI: does NOT immediately invalidate completed stages
    model.update_step_params(PipelineStep.ROI, z_start=10, z_end=100)
    assert model.get_step_params(PipelineStep.ROI) == {"z_start": 10, "z_end": 100}
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.COMPLETED

    # When ROI executes again (transitions to RUNNING), subsequent steps are invalidated to IDLE
    model.set_step_status(PipelineStep.ROI, StepStatus.RUNNING)
    assert model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE

    # Direct invalidate_subsequent helper resets downstream steps
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)
    model.invalidate_subsequent(PipelineStep.ROI)
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE


def test_pipeline_model_is_step_dirty_and_invalidate_from() -> None:
    model = PipelineModel()
    model.update_step_params(PipelineStep.ROI, val=10)
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    assert not model.is_step_dirty(PipelineStep.ROI)

    # Change parameter while completed -> becomes dirty
    model.update_step_params(PipelineStep.ROI, val=20)
    assert model.is_step_dirty(PipelineStep.ROI)

    # Invalidate from ROI resets ROI and downstream steps
    model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)
    model.invalidate_from(PipelineStep.ROI)
    assert model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE
    assert not model.is_step_dirty(PipelineStep.ROI)


def test_pipeline_model_plan_execution() -> None:
    model = PipelineModel()

    # Plan from scratch: all steps should become PENDING
    planned = model.plan_execution()
    assert planned == list(PIPELINE_STEP_ORDER)
    for step in PIPELINE_STEP_ORDER:
        assert model.get_status(step) == StepStatus.PENDING

    # Complete ROI
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    # Plan execution: remaining steps should remain PENDING
    planned = model.plan_execution()
    assert planned == list(PIPELINE_STEP_ORDER[1:])
    assert model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING

    # Plan up to intermediate step: Preprocessing up to Detection
    model.reset_all()
    planned = model.plan_execution(from_step=PipelineStep.ROI, to_step=PipelineStep.DETECTION)
    assert planned == [PipelineStep.ROI, PipelineStep.PREPROCESSING, PipelineStep.DETECTION]
    assert model.get_status(PipelineStep.ROI) == StepStatus.PENDING
    assert model.get_status(PipelineStep.PREPROCESSING) == StepStatus.PENDING
    assert model.get_status(PipelineStep.DETECTION) == StepStatus.PENDING
    assert model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert model.get_status(PipelineStep.BATCH) == StepStatus.IDLE

    # When all complete, plan_execution does nothing
    for step in PIPELINE_STEP_ORDER:
        if model.get_status(step) != StepStatus.COMPLETED:
            model.set_step_status(step, StepStatus.COMPLETED)
    assert model.is_complete

    assert model.plan_execution() == []
    assert model.is_complete


def test_pipeline_model_reset_all(qtbot) -> None:
    model = PipelineModel()
    model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)

    with qtbot.waitSignal(model.pipeline_reset):
        model.reset_all()

    for step in PIPELINE_STEP_ORDER:
        assert model.get_status(step) == StepStatus.IDLE


def test_pipeline_model_preproc_params(qtbot) -> None:
    model = PipelineModel()
    defaults = PreprocParams()
    assert model.get_preproc_params() == defaults

    custom = PreprocParams(
        denoise_xy_scale_um=3.5,
        bg_mode=BgMode.PERCENTILE_PER_SLICE,
        bg_percentile=60.0,
        lowest_intensity=20.0,
        highest_intensity=800.0,
    )

    with qtbot.waitSignal(model.step_params_changed) as blocker:
        model.set_preproc_params(custom)
    assert blocker.args == [PipelineStep.PREPROCESSING]
    assert model.get_preproc_params() == custom
