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


class PipelineController(QObject):
    """
    Single point of entry for orchestrating pipeline execution and updating the right panel.

    Connects the PipelineModel to the RightPanel view:
    - Propagates model status and parameter events to the view.
    - Handles user actions from the view (stage execution up to target).
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
        self._view.execute_stage_requested.connect(self.run_up_to)
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

    def run_up_to(self, target_step: PipelineStep | str) -> None:
        """
        Execute the pipeline from the first incomplete step up to `target_step` (inclusive).

        Args:
            target_step: The target PipelineStep or step string.
        """
        if isinstance(target_step, str):
            try:
                target_step = PipelineStep(target_step)
            except ValueError:
                return

        target_title = target_step.value.replace("_", " ").title()

        if self._model.get_status(target_step) == StepStatus.COMPLETED:
            self._view.set_stats_summary(texts.STATS_COMPLETED_UP_TO_SUMMARY.format(step=target_title))
            self._view.set_stats_details(texts.STATS_ALREADY_COMPLETED.format(step=target_title))
            return

        target_idx = PIPELINE_STEP_ORDER.index(target_step)

        # Find first incomplete step up to target
        first_incomplete: PipelineStep | None = None
        for step in PIPELINE_STEP_ORDER[: target_idx + 1]:
            if self._model.get_status(step) != StepStatus.COMPLETED:
                first_incomplete = step
                break

        if first_incomplete is None:
            return

        self._target_step = target_step

        # Plan incomplete steps up to target as PENDING
        self._model.plan_execution(from_step=first_incomplete, to_step=target_step)

        # Start the first incomplete step as RUNNING
        self._model.set_step_status(first_incomplete, StepStatus.RUNNING)
        self._update_stats_for_running(first_incomplete, target_step)

    def run_pipeline(self) -> None:
        """Initiate or resume execution through all pipeline stages."""
        self.run_up_to(PIPELINE_STEP_ORDER[-1])

    def complete_step(self, step: PipelineStep) -> None:
        """
        Mark `step` as COMPLETED and automatically advance to next step if target not reached.

        Args:
            step: Step to mark as completed.
        """
        self._model.set_step_status(step, StepStatus.COMPLETED)
        step_title = step.value.replace("_", " ").title()

        if step == self._target_step:
            # Reached target of this run
            self._target_step = None
            if self._model.is_complete:
                self._view.set_stats_summary(texts.STATS_COMPLETED_SUMMARY)
                self._view.set_stats_details(texts.STATS_COMPLETED_DETAILS)
            else:
                self._view.set_stats_summary(texts.STATS_COMPLETED_UP_TO_SUMMARY.format(step=step_title))
                self._view.set_stats_details(texts.STATS_COMPLETED_UP_TO_DETAILS.format(step=step_title))
            return

        # Advance to next step if queued
        idx = PIPELINE_STEP_ORDER.index(step)
        next_idx = idx + 1
        if next_idx < len(PIPELINE_STEP_ORDER):
            next_step = PIPELINE_STEP_ORDER[next_idx]
            if self._model.get_status(next_step) == StepStatus.PENDING:
                self._model.set_step_status(next_step, StepStatus.RUNNING)
                target = self._target_step or PIPELINE_STEP_ORDER[-1]
                self._update_stats_for_running(next_step, target)
        else:
            self._target_step = None
            self._view.set_stats_summary(texts.STATS_COMPLETED_SUMMARY)
            self._view.set_stats_details(texts.STATS_COMPLETED_DETAILS)

    def run_step(self, step_name: str) -> None:
        """
        Run a single pipeline step by delegating to `run_up_to`.

        Args:
            step_name: Name of the step to run.
        """
        self.run_up_to(step_name)

    def reset_pipeline(self) -> None:
        """Reset all stages to IDLE and clear stats."""
        self._target_step = None
        self._model.reset_all()

    def _sync_view(self) -> None:
        """Synchronize the view with current model statuses."""
        for step in PIPELINE_STEP_ORDER:
            self._view.set_step_status(step, self._model.get_status(step))

    def _on_step_status_changed(self, step: PipelineStep, status: StepStatus) -> None:
        """Handle status updates emitted by the model."""
        self._view.set_step_status(step, status)

    def _on_pipeline_reset(self) -> None:
        """Handle model reset event."""
        self._target_step = None
        self._view.set_stats_summary(texts.STATS_DEFAULT_SUMMARY)
        self._view.set_stats_details(texts.STATS_DEFAULT_DETAILS)
        for step in PIPELINE_STEP_ORDER:
            self._view.set_step_status(step, StepStatus.IDLE)

    def _on_view_param_changed(self, step_name: str, param_name: str, value: Any) -> None:
        """Handle parameter adjustments from the view."""
        try:
            step = PipelineStep(step_name)
        except ValueError:
            return
        self._model.update_step_params(step, **{param_name: value})

    def _update_stats_for_running(self, step: PipelineStep, target: PipelineStep) -> None:
        """Update bottom stats bar to reflect the active step and target."""
        step_title = step.value.replace("_", " ").title()
        target_title = target.value.replace("_", " ").title()
        self._view.set_stats_summary(texts.STATS_WORKING_SUMMARY.format(step=step_title))
        self._view.set_stats_details(texts.STATS_WORKING_DETAILS.format(step=step_title, target=target_title))
