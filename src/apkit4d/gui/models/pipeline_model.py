"""
Model representing the analysis pipeline state, stage dependencies, and execution status.
"""

import copy
from enum import StrEnum
from typing import Any

from PySide6.QtCore import QObject, Signal


class StepStatus(StrEnum):
    """Execution status for a pipeline step."""

    IDLE = "idle"  # Default state: unexecuted or reset
    PENDING = "pending"  # Planned for execution / queued (Blue)
    RUNNING = "running"  # In progress / executing (Orange)
    COMPLETED = "completed"  # Successfully processed (Green)


class PipelineStep(StrEnum):
    """The ordered stages of the apkit4d processing pipeline."""

    ROI = "roi"
    PREPROCESSING = "preprocessing"
    DETECTION = "detection"
    TRACKING = "tracking"
    BATCH = "batch"


PIPELINE_STEP_ORDER: tuple[PipelineStep, ...] = (
    PipelineStep.ROI,
    PipelineStep.PREPROCESSING,
    PipelineStep.DETECTION,
    PipelineStep.TRACKING,
    PipelineStep.BATCH,
)


class PipelineModel(QObject):
    """
    Manages the pipeline state and enforces sequential execution dependencies.

    Invariants enforced:
    1. A step cannot be marked COMPLETED or RUNNING unless all previous steps are COMPLETED.
    2. If a step's parameters or status change away from COMPLETED, all subsequent steps
       are automatically invalidated and reset to IDLE.
    3. An IDLE, PENDING, or RUNNING step cannot exist before a COMPLETED step.

    Signals:
        step_status_changed: Emitted with (PipelineStep, StepStatus) when a step's status updates.
        step_params_changed: Emitted with (PipelineStep) when a step's configuration is modified.
        pipeline_reset: Emitted when all pipeline steps are reset to IDLE.
    """

    step_status_changed = Signal(object, object)
    step_params_changed = Signal(object)
    pipeline_reset = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._statuses: dict[PipelineStep, StepStatus] = {
            step: StepStatus.IDLE for step in PIPELINE_STEP_ORDER
        }
        self._params: dict[PipelineStep, dict[str, Any]] = {step: {} for step in PIPELINE_STEP_ORDER}
        self._last_run_params: dict[PipelineStep, dict[str, Any]] = {step: {} for step in PIPELINE_STEP_ORDER}

    @property
    def step_order(self) -> tuple[PipelineStep, ...]:
        """Ordered sequence of pipeline stages."""
        return PIPELINE_STEP_ORDER

    @property
    def statuses(self) -> dict[PipelineStep, StepStatus]:
        """Mapping of each pipeline step to its current status."""
        return dict(self._statuses)

    @property
    def is_complete(self) -> bool:
        """True if all steps in the pipeline have completed."""
        return all(s == StepStatus.COMPLETED for s in self._statuses.values())

    @property
    def active_step(self) -> PipelineStep | None:
        """The currently running step, or None if no step is running."""
        for step in PIPELINE_STEP_ORDER:
            if self._statuses[step] == StepStatus.RUNNING:
                return step
        return None

    @property
    def current_running_step(self) -> PipelineStep | None:
        """Convenience alias for active_step."""
        return self.active_step

    def get_status(self, step: PipelineStep) -> StepStatus:
        """
        Return the current execution status of a step.

        Args:
            step: The pipeline step to inspect.
        """
        return self._statuses[step]

    def can_run_step(self, step: PipelineStep) -> bool:
        """
        Return True if all prerequisites for running this step are met.

        Args:
            step: Step to check.
        """
        idx = PIPELINE_STEP_ORDER.index(step)
        for prev_step in PIPELINE_STEP_ORDER[:idx]:
            if self._statuses[prev_step] != StepStatus.COMPLETED:
                return False
        return self._statuses[step] != StepStatus.RUNNING

    def set_step_status(self, step: PipelineStep, status: StepStatus) -> None:
        """
        Set status for `step`, enforcing sequential dependency and cascading invalidation rules.

        Args:
            step: The step to update.
            status: The new status.

        Raises:
            ValueError: If attempting to set COMPLETED or RUNNING when prior steps are incomplete.
        """
        current_status = self._statuses[step]
        if current_status == status:
            return

        idx: int = PIPELINE_STEP_ORDER.index(step)

        # Invariant check: Cannot mark COMPLETED or RUNNING if any prior step is incomplete
        if status in (StepStatus.COMPLETED, StepStatus.RUNNING):
            for prev_step in PIPELINE_STEP_ORDER[:idx]:
                if self._statuses[prev_step] != StepStatus.COMPLETED:
                    raise ValueError(
                        f"Cannot set '{step.value}' to {status.value}: "
                        f"prior step '{prev_step.value}' is not completed."
                    )

        # Invariant check: If step was COMPLETED and transitions away, or transitions to IDLE,
        # invalidate all subsequent steps to IDLE.
        if (
            current_status == StepStatus.COMPLETED and status != StepStatus.COMPLETED
        ) or status == StepStatus.IDLE:
            self._invalidate_subsequent(idx)
        elif status == StepStatus.RUNNING:
            for later_step in PIPELINE_STEP_ORDER[idx + 1 :]:
                if self._statuses[later_step] == StepStatus.COMPLETED:
                    self._statuses[later_step] = StepStatus.IDLE
                    self.step_status_changed.emit(later_step, StepStatus.IDLE)

        self._statuses[step] = status
        if status == StepStatus.COMPLETED:
            self._last_run_params[step] = copy.deepcopy(self._params[step])
        self.step_status_changed.emit(step, status)

    def is_step_dirty(self, step: PipelineStep) -> bool:
        """
        Return True if a completed step's parameters were modified after completion.

        Args:
            step: The step to check.
        """
        if self._statuses[step] != StepStatus.COMPLETED:
            return False
        return self._params[step] != self._last_run_params.get(step, {})

    def update_step_params(self, step: PipelineStep, **params: Any) -> None:
        """
        Update configuration parameters for `step`.

        Updating parameters does not immediately invalidate completed stages,
        preventing accidental parameter adjustments from discarding hours of processing.
        Invalidation occurs when the stage is executed again or planned for rework.

        Args:
            step: Step whose parameters changed.
            params: Key-value parameters.
        """
        self._params[step].update(params)
        self.step_params_changed.emit(step)

    def invalidate_subsequent(self, step: PipelineStep) -> None:
        """
        Invalidate all steps following `step`, resetting their status to IDLE.

        Called when `step` is re-executed, ensuring stale downstream results
        are cleared.

        Args:
            step: Step whose downstream stages should be invalidated.
        """
        idx = PIPELINE_STEP_ORDER.index(step)
        self._invalidate_subsequent(idx)

    def invalidate_from(self, step: PipelineStep) -> None:
        """
        Invalidate `step` and all steps following it, resetting their status to IDLE.

        Called when a completed step with modified parameters is planned for rework.

        Args:
            step: Earliest pipeline step to invalidate.
        """
        idx = PIPELINE_STEP_ORDER.index(step)
        for s in PIPELINE_STEP_ORDER[idx:]:
            if self._statuses[s] != StepStatus.IDLE:
                self._statuses[s] = StepStatus.IDLE
                self._last_run_params[s] = {}
                self.step_status_changed.emit(s, StepStatus.IDLE)

    def get_step_params(self, step: PipelineStep) -> dict[str, Any]:
        """Return a copy of the configuration dictionary for `step`."""
        return dict(self._params[step])

    def plan_execution(
        self,
        from_step: PipelineStep | None = None,
        to_step: PipelineStep | None = None,
    ) -> list[PipelineStep]:
        """
        Plan pipeline execution starting from `from_step` up to `to_step` (inclusive).

        Sets incomplete steps to PENDING.

        Args:
            from_step: Starting step. If None, starts from the first incomplete step.
            to_step: Ending step (inclusive). If None, plans through the last step.

        Returns:
            List of steps included in the execution plan from `from_step` to `to_step`.
        """
        start_step = from_step
        if start_step is None:
            for s in PIPELINE_STEP_ORDER:
                if self._statuses[s] != StepStatus.COMPLETED:
                    start_step = s
                    break

        if start_step is None:
            return []  # Already all completed

        start_idx = PIPELINE_STEP_ORDER.index(start_step)
        end_idx = PIPELINE_STEP_ORDER.index(to_step) + 1 if to_step is not None else len(PIPELINE_STEP_ORDER)
        planned_steps: list[PipelineStep] = []
        for s in PIPELINE_STEP_ORDER[start_idx:end_idx]:
            planned_steps.append(s)
            if self._statuses[s] not in (StepStatus.RUNNING, StepStatus.COMPLETED):
                self._statuses[s] = StepStatus.PENDING
                self.step_status_changed.emit(s, StepStatus.PENDING)
        return planned_steps

    def reset_all(self) -> None:
        """Reset all steps to IDLE status."""
        self._last_run_params = {step: {} for step in PIPELINE_STEP_ORDER}
        for step in PIPELINE_STEP_ORDER:
            if self._statuses[step] != StepStatus.IDLE:
                self._statuses[step] = StepStatus.IDLE
                self.step_status_changed.emit(step, StepStatus.IDLE)
        self.pipeline_reset.emit()

    def _invalidate_subsequent(self, step_idx: int) -> None:
        """Helper to reset all steps following `step_idx` to IDLE."""
        for later_step in PIPELINE_STEP_ORDER[step_idx + 1 :]:
            if self._statuses[later_step] != StepStatus.IDLE:
                self._statuses[later_step] = StepStatus.IDLE
                self.step_status_changed.emit(later_step, StepStatus.IDLE)
