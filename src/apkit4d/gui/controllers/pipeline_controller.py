"""
Controller managing the analysis pipeline, bridging PipelineModel and RightPanel.
"""

from typing import Any

from PySide6.QtCore import QObject

from apkit4d.gui.constants import texts
from apkit4d.gui.models.pipeline_model import (
    PIPELINE_STEP_ORDER,
    PipelineModel,
    PipelineStep,
    StepStatus,
)
from apkit4d.gui.views.panels.right_panel import RightPanel


def _format_step_title(step: PipelineStep) -> str:
    """
    Format pipeline step enum member into display title.

    Args:
        step: Pipeline step.

    Returns:
        Formatted title string (e.g., 'ROI', 'Preprocessing').
    """
    if step == PipelineStep.ROI:
        return "ROI"
    return step.value.replace("_", " ").title()


class PipelineController(QObject):
    """
    Single point of entry for orchestrating pipeline execution and updating the right panel.

    Connects the PipelineModel to the RightPanel view:
    - Propagates model status and parameter events to the view.
    - Handles interactive stage planning, completion, and parameter adjustments.
    - Enforces sequential execution and cascading invalidation.

    Args:
        model: The underlying pipeline state model.
        view: The right panel view.
        parent: Optional Qt parent object.
    """

    def __init__(
        self,
        model: PipelineModel,
        view: RightPanel,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._view = view
        self._target_step: PipelineStep | None = None

        # 1. Connect Model events -> View
        self._model.step_status_changed.connect(self._on_step_status_changed)
        self._model.pipeline_reset.connect(self._on_pipeline_reset)

        # 2. Connect View events -> Controller / Model
        self._view.plan_stage_requested.connect(self.plan_up_to)
        self._view.run_stage_requested.connect(self.run_up_to)
        self._view.complete_stage_requested.connect(self.complete_stage)
        self._view.step_param_changed.connect(self._on_view_param_changed)

        # Synchronize initial state
        self._sync_view()

    @property
    def model(self) -> PipelineModel:
        """The underlying pipeline model."""
        return self._model

    @property
    def view(self) -> RightPanel:
        """The controlled right panel view."""
        return self._view

    @property
    def target_step(self) -> PipelineStep | None:
        """The target step of the current execution run, or None."""
        return self._target_step

    def plan_up_to(self, target_step: PipelineStep | str) -> None:
        """
        Plan execution from the earliest unexecuted or modified step up to `target_step` (inclusive).

        Sets steps up to `target_step` as PENDING (blue). If any completed step
        up to `target_step` had its parameters modified, it is assumed it will be reworked,
        so that step and all downstream steps are invalidated to IDLE before planning.

        Args:
            target_step: The target PipelineStep or step string.
        """
        if isinstance(target_step, str):
            try:
                target_step = PipelineStep(target_step)
            except ValueError:
                return

        target_idx = PIPELINE_STEP_ORDER.index(target_step)

        # Check if any completed step up to target has modified parameters (dirty)
        first_dirty: PipelineStep | None = None
        for step in PIPELINE_STEP_ORDER[: target_idx + 1]:
            if self._model.is_step_dirty(step):
                first_dirty = step
                break

        if first_dirty is not None:
            # We assume it will be reworked; invalidate from this step onwards
            self._model.invalidate_from(first_dirty)
            first_step_to_plan = first_dirty
        else:
            # Find first incomplete step up to target
            first_incomplete: PipelineStep | None = None
            for step in PIPELINE_STEP_ORDER[: target_idx + 1]:
                if self._model.get_status(step) != StepStatus.COMPLETED:
                    first_incomplete = step
                    break

            if first_incomplete is None:
                return  # All steps up to target are completed and clean

            first_step_to_plan = first_incomplete

        self._target_step = target_step
        self._model.plan_execution(from_step=first_step_to_plan, to_step=target_step)
        self._update_pipeline_stats()

    def complete_stage(self, step: PipelineStep | str) -> None:
        """
        Mark `step` as COMPLETED, verifying that all prior stages are completed.

        If the next step was planned (PENDING), it automatically transitions to RUNNING.
        If prior stages are not completed, the request is ignored without displaying errors.

        Args:
            step: Step to mark as completed.
        """
        if isinstance(step, str):
            try:
                step = PipelineStep(step)
            except ValueError:
                return

        # Check prerequisite invariant: all prior steps must be COMPLETED
        step_idx = PIPELINE_STEP_ORDER.index(step)
        for prev_step in PIPELINE_STEP_ORDER[:step_idx]:
            if self._model.get_status(prev_step) != StepStatus.COMPLETED:
                # Prerequisite stages incomplete; ignore request without displaying errors
                return

        # If already COMPLETED, re-completing it executes it again and invalidates subsequent stages
        if self._model.get_status(step) == StepStatus.COMPLETED:
            self._model.invalidate_subsequent(step)
            self._update_pipeline_stats()
            return

        self._model.set_step_status(step, StepStatus.COMPLETED)

        # Advance to next step if queued as PENDING
        next_idx = step_idx + 1
        if next_idx < len(PIPELINE_STEP_ORDER):
            next_step = PIPELINE_STEP_ORDER[next_idx]
            if self._model.get_status(next_step) == StepStatus.PENDING:
                self._model.set_step_status(next_step, StepStatus.RUNNING)

        self._update_pipeline_stats()

    def complete_step(self, step: PipelineStep) -> None:
        """Convenience alias for complete_stage."""
        self.complete_stage(step)

    def run_up_to(self, target_step: PipelineStep | str) -> None:
        """
        Execute the pipeline from the first incomplete step up to `target_step` (inclusive).

        Args:
            target_step: The target PipelineStep or step string.
        """
        self.plan_up_to(target_step)
        if isinstance(target_step, str):
            try:
                target_step = PipelineStep(target_step)
            except ValueError:
                return

        for step in PIPELINE_STEP_ORDER:
            if self._model.get_status(step) == StepStatus.PENDING:
                self._model.set_step_status(step, StepStatus.RUNNING)
                break
        self._update_pipeline_stats()

    def run_pipeline(self) -> None:
        """Initiate or resume execution through all pipeline stages."""
        self.run_up_to(PIPELINE_STEP_ORDER[-1])

    def reset_pipeline(self) -> None:
        """Reset all stages to IDLE and clear stats."""
        self._target_step = None
        self._model.reset_all()

    def _sync_view(self) -> None:
        """Synchronize the view with current model statuses and statistics."""
        for step in PIPELINE_STEP_ORDER:
            self._view.set_step_status(step, self._model.get_status(step))
        self._update_pipeline_stats()

    def _on_step_status_changed(self, step: PipelineStep, status: StepStatus) -> None:
        """Handle status updates emitted by the model."""
        self._view.set_step_status(step, status)

    def _on_pipeline_reset(self) -> None:
        """Handle model reset event."""
        self._target_step = None
        for step in PIPELINE_STEP_ORDER:
            self._view.set_step_status(step, StepStatus.IDLE)
        self._update_pipeline_stats()

    def _on_view_param_changed(self, step_name: str, param_name: str, value: Any) -> None:
        """Handle parameter adjustments from the view."""
        try:
            step = PipelineStep(step_name)
        except ValueError:
            return
        self._model.update_step_params(step, **{param_name: value})
        self._update_pipeline_stats()

    def _update_pipeline_stats(self) -> None:
        """
        Update the bottom statistics pane to reflect the current state of work.

        Shows what the pipeline is currently doing (if a step is running) or what
        has been completed, avoiding transient event logs or error messages.
        """
        running_step: PipelineStep | None = None
        completed_steps: list[PipelineStep] = []

        for step in PIPELINE_STEP_ORDER:
            status = self._model.get_status(step)
            if status == StepStatus.RUNNING:
                running_step = step
            elif status == StepStatus.COMPLETED:
                completed_steps.append(step)

        # Active execution in progress: show what it is doing
        if running_step is not None:
            step_title = _format_step_title(running_step)
            self._view.set_stats_summary(texts.STATS_WORKING_SUMMARY.format(step=step_title))
            completed_str = (
                ", ".join(_format_step_title(s) for s in completed_steps) if completed_steps else "None"
            )
            target = self._target_step or running_step
            target_str = _format_step_title(target)
            self._view.set_stats_details(
                texts.STATS_WORKING_DETAILS.format(
                    step=step_title,
                    completed=completed_str,
                    target=target_str,
                )
            )
            return

        total = len(PIPELINE_STEP_ORDER)

        # All stages completed
        if len(completed_steps) == total:
            self._target_step = None
            self._view.set_stats_summary(texts.STATS_COMPLETED_SUMMARY)
            self._view.set_stats_details(texts.STATS_COMPLETED_DETAILS)
            return

        # Some stages completed
        if completed_steps:
            completed_str = ", ".join(_format_step_title(s) for s in completed_steps)
            self._view.set_stats_summary(
                texts.STATS_COMPLETED_PROGRESS_SUMMARY.format(
                    completed=len(completed_steps),
                    total=total,
                )
            )
            self._view.set_stats_details(
                texts.STATS_COMPLETED_PROGRESS_DETAILS.format(
                    completed_count=len(completed_steps),
                    total=total,
                    completed_stages=completed_str,
                )
            )
            return

        # Idle / nothing completed
        self._view.set_stats_summary(texts.STATS_DEFAULT_SUMMARY)
        self._view.set_stats_details(texts.STATS_DEFAULT_DETAILS)
