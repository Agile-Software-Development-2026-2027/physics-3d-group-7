"""Controller for asynchronous trajectory linking and Stage 4 pipeline orchestration."""

import logging
from functools import partial
from typing import cast

import pandas as pd
from PySide6.QtCore import QObject, Signal

from apkit4d.core.models import TrackingConfig
from apkit4d.gui.controllers.file_controller import FileController
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.trajectory_controller import TrajectoryController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep, StepStatus
from apkit4d.tracking.linker import ParticleLinker, TrackingResult

logger = logging.getLogger(__name__)


class TrajectoryLinkingController(QObject):
    """Run particle tracking and coordinate Stage 4 pipeline execution."""

    result_ready = Signal(object)
    failed = Signal(object)

    def __init__(
        self,
        parent: QObject | None = None,
        *,
        pipeline_model: PipelineModel | None = None,
        pipeline_controller: PipelineController | None = None,
        file_controller: FileController | None = None,
        trajectory_controller: TrajectoryController | None = None,
        playback_controller: PlaybackController | None = None,
    ) -> None:
        super().__init__(parent)

        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_success)
        self._runner.failed.connect(self._on_failure)

        self._pipeline_model = pipeline_model
        self._pipeline_controller = pipeline_controller
        self._file_controller = file_controller
        self._trajectory_controller = trajectory_controller
        self._playback_controller = playback_controller

        self._task_id: int | None = None
        self.result: TrackingResult | None = None
        self._tracking_running_config: TrackingConfig | None = None
        self._tracking_generation = 0
        self._tracking_running_generation: int | None = None

        if self._pipeline_model is not None:
            self._pipeline_model.pipeline_reset.connect(self._on_pipeline_reset)
            self._pipeline_model.step_status_changed.connect(self._on_step_status_changed)

    @property
    def is_running(self) -> bool:
        """Whether a linking task is currently running."""
        return self._task_id is not None

    def run(
        self,
        detections: pd.DataFrame,
        config: TrackingConfig,
        dt_s: float | None = None,
    ) -> bool:
        """Start linking detections in a background thread."""
        if self.is_running:
            return False

        self.result = None

        self._task_id = self._runner.run(
            partial(
                ParticleLinker(config).link,
                detections,
                dt_s=dt_s,
            )
        )
        return True

    def set_precomputed_result(
        self,
        result: TrackingResult | None,
        *,
        dt_s: float | None = None,
        current_frame: int = 0,
    ) -> None:
        """Populate tracking result from a precomputed session and update 3D trajectories."""
        self.result = result
        if self._trajectory_controller is not None:
            if result is not None:
                self._trajectory_controller.set_trajectories(
                    result.tracks,
                    dt_s=dt_s,
                    current_frame=current_frame,
                )
            else:
                self._trajectory_controller.clear_source()

    def clear_result(self) -> None:
        """Clear stored tracking results and displayed 3D trajectories."""
        self.result = None
        if self._trajectory_controller is not None:
            self._trajectory_controller.clear_source()

    def _on_step_status_changed(self, step: PipelineStep, status: StepStatus) -> None:
        if step != PipelineStep.TRACKING:
            return

        if status != StepStatus.COMPLETED:
            self.clear_result()

        if status == StepStatus.RUNNING:
            self._start_tracking_if_needed()
        else:
            self._tracking_generation += 1

    def _on_pipeline_reset(self) -> None:
        self._tracking_generation += 1
        self.clear_result()

    def _start_tracking_if_needed(self) -> None:
        """Link detections produced by Stage 3 using current Stage 4 configuration."""
        if self._pipeline_model is None:
            return
        if self._pipeline_model.get_status(PipelineStep.TRACKING) != StepStatus.RUNNING:
            return
        if self.is_running:
            return

        config = TrackingConfig(**self._pipeline_model.get_step_params(PipelineStep.TRACKING))
        batch_results = self._pipeline_model.batch_results
        if batch_results is None:
            self._tracking_running_config = config
            self._tracking_running_generation = self._tracking_generation
            self._handle_pipeline_failure(
                ValueError("No detections available. Run the Detection stage first.")
            )
            return

        detections, metadata = batch_results
        dt_s = metadata.get("info", {}).get("dt_s")

        self._tracking_running_config = config
        self._tracking_running_generation = self._tracking_generation

        try:
            self.run(detections, config, dt_s=dt_s)
            logger.debug("Started Stage 4 trajectory linking (generation=%d)", self._tracking_generation)
        except Exception as error:
            self._handle_pipeline_failure(error)

    def _tracking_result_is_current(self) -> bool:
        """Check whether the in-flight task still matches current Stage 4 state and config."""
        if self._pipeline_model is None:
            return True
        if self._tracking_running_generation != self._tracking_generation:
            return False
        if self._pipeline_model.get_status(PipelineStep.TRACKING) != StepStatus.RUNNING:
            return False

        current_config = TrackingConfig(**self._pipeline_model.get_step_params(PipelineStep.TRACKING))
        return current_config == self._tracking_running_config

    def _on_success(self, task_id: int, result: object) -> None:
        if task_id != self._task_id:
            return

        self._task_id = None
        if self._pipeline_model is not None and not self._tracking_result_is_current():
            self._start_tracking_if_needed()
            return

        tracking_result = cast(TrackingResult, result)
        self.result = tracking_result
        self.result_ready.emit(self.result)

        if self._pipeline_model is None:
            return

        if self._trajectory_controller is not None:
            dt_s = (
                self._file_controller.source.info.dt_s
                if self._file_controller is not None and self._file_controller.source is not None
                else None
            )
            current_frame = self._playback_controller.frame if self._playback_controller is not None else 0
            self._trajectory_controller.set_trajectories(
                tracking_result.tracks,
                dt_s=dt_s,
                current_frame=current_frame,
            )

        if self._pipeline_controller is not None:
            self._pipeline_controller.complete_stage(PipelineStep.TRACKING)
        logger.info("Completed Stage 4 trajectory linking (%d rows)", len(tracking_result.tracks))

    def _on_failure(self, task_id: int, error: object) -> None:
        if task_id != self._task_id:
            return

        self._task_id = None
        if self._pipeline_model is not None:
            if not self._tracking_result_is_current():
                self._start_tracking_if_needed()
                return
            self._handle_pipeline_failure(error)

        self.failed.emit(error)

    def _handle_pipeline_failure(self, error: object) -> None:
        self.clear_result()
        if self._pipeline_model is not None:
            self._pipeline_model.invalidate_from(PipelineStep.TRACKING)

        reason = str(error) or type(error).__name__
        if self._pipeline_controller is not None:
            self._pipeline_controller.report_stage_failure("Trajectory linking failed", reason)
        logger.warning("Stage 4 trajectory linking failed: %s", reason)
