"""
Controller of the main window.

It is the only place where the view meets the rest of the application. It creates the other controllers
and connects them: the `FileController` opens the files, the `PlaybackController` moves through the
frames, the `VolumeController` shows them in the 3D view, the `AppearanceController` changes how the
3D view looks, the `ThemeController` changes the look of the application, and the `PipelineController`
orchestrates the analysis pipeline.
"""

from functools import partial
from pathlib import Path
from typing import Protocol, cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from apkit4d.core.models import TrackingConfig
from apkit4d.core.roi import Bounds6D, RegionOfInterest
from apkit4d.detection.blob_detection import BlobParams
from apkit4d.detection.preprocessing import PreprocParams
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.appearance_controller import AppearanceController, AppearanceView
from apkit4d.gui.controllers.batch_controller import BatchController
from apkit4d.gui.controllers.blob_detection_controller import BlobDetectionController, BlobView
from apkit4d.gui.controllers.file_controller import FileController, FrameSource, SourceOpener
from apkit4d.gui.controllers.histogram_controller import HistogramController
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.seed_histogram_controller import SeedHistogramController
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.theme_controller import ThemeController
from apkit4d.gui.controllers.trajectory_controller import TrajectoryController, TrajectoryView
from apkit4d.gui.controllers.trajectory_detection import DetectionData, detect_sequence
from apkit4d.gui.controllers.trajectory_linking_controller import (
    TrajectoryLinkingController,
)
from apkit4d.gui.controllers.video_export_controller import (
    VideoExportController,
    VideoExportView,
)
from apkit4d.gui.controllers.volume_controller import RoiSelectionView, VolumeController, VolumeView
from apkit4d.gui.models.pipeline_model import (
    PIPELINE_STEP_ORDER,
    PipelineModel,
    PipelineStep,
    StepStatus,
)
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.stages.preprocessing_section import PreprocessingSection
from apkit4d.io.czi import CziSource
from apkit4d.io.mock import MockConfig, create_mock_source
from apkit4d.io.session import PrecomputedSession, PrecomputedSource, infer_completed_steps
from apkit4d.tracking.linker import TrackingResult


class SceneView(VolumeView, AppearanceView, BlobView, TrajectoryView, VideoExportView, Protocol):
    """What the controllers need from the 3D view: showing the frames and changing how they look."""


class MainController(QObject):
    """
    Connects the signals of the main window to the application logic.

    Args:
        window: The view to control.
        app: The application, whose look is controlled by the theme.
        parent: Qt parent, so the controller lives as long as the window.
        open_source: Function that opens a file and returns its recording, `CziSource` unless a test
            needs a fake one.
        view: The 3D view that shows the frames. Without it the recording is opened but not shown.
    """

    def __init__(
        self,
        window: MainWindow,
        app: QApplication,
        parent: QObject | None = None,
        *,
        open_source: SourceOpener = CziSource,
        view: SceneView | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._file_controller = FileController(window, open_source, self)
        self._playback_controller = PlaybackController(window.playback_bar, self)
        self._theme_controller = ThemeController(app, self)
        self._pipeline_model = PipelineModel(self)
        self._pipeline_controller = PipelineController(self._pipeline_model, window.right_panel, self)
        self._detection_runner = TaskRunner(self)
        self._detection_runner.succeeded.connect(self._on_detection_ready)
        self._detection_runner.failed.connect(self._on_detection_failed)

        self._detection_task: int | None = None
        self._detection_generation = 0
        self._detection_running_generation: int | None = None
        self._detection_running_source: FrameSource | None = None

        self._detection_running_params: tuple[PreprocParams, BlobParams, RegionOfInterest | None] | None = (
            None
        )

        self._tracking_controller = TrajectoryLinkingController(self)
        self._tracking_controller.result_ready.connect(self._on_tracking_ready)
        self._tracking_controller.failed.connect(self._on_tracking_failed)

        self._tracking_result: TrackingResult | None = None
        self._tracking_running_config: TrackingConfig | None = None
        self._tracking_generation = 0
        self._tracking_running_generation: int | None = None

        self._pipeline_model.pipeline_reset.connect(self._on_detection_pipeline_reset)
        self._pipeline_model.pipeline_reset.connect(self._on_tracking_pipeline_reset)

        self._pipeline_model.step_status_changed.connect(self._on_detection_step_status_changed)
        self._pipeline_model.step_status_changed.connect(self._on_tracking_step_status_changed)

        self._volume_controller = VolumeController(window, view, self) if view is not None else None
        if self._volume_controller is not None:
            # the volume controller must know the new recording before the playback goes back to frame 0
            self._file_controller.loaded.connect(self._volume_controller.set_source)
            self._playback_controller.frame_changed.connect(self._volume_controller.show_frame)
            self._volume_controller.failed.connect(self._on_volume_failed)
            window.playback_bar.reset_camera_requested.connect(self._volume_controller.reset_camera)
            self.pipeline_model.step_params_changed.connect(self._on_step_params_changed)
            self._volume_controller.window_suggested.connect(self._on_window_suggested)

            if preproc_sec := self.pipeline_controller.view.get_section(PipelineStep.PREPROCESSING):
                cast(PreprocessingSection, preproc_sec).suggest_window_clicked.connect(
                    self._on_suggest_window_clicked
                )

        preproc_section = (
            cast(
                PreprocessingSection,
                self.pipeline_controller.view.get_section(PipelineStep.PREPROCESSING),
            )
            if hasattr(self.pipeline_controller.view, "get_section")
            else None
        )
        self._histogram_controller = HistogramController(
            window.left_panel.histograms_section._roi_histogram,
            self._volume_controller,
            self._pipeline_model,
            preproc_histogram=window.left_panel.histograms_section._preproc_histogram,
            preproc_section=preproc_section,
            parent=self,
        )

        self._blob_controller: BlobDetectionController | None = None
        if (
            view is not None
            and self._volume_controller is not None
            and (detection_inspector := window.right_panel.detection_inspector)
        ):
            self._blob_controller = BlobDetectionController(detection_inspector, view, parent=self)
            self._volume_controller.volume_prepared.connect(self._blob_controller.on_volume_prepared)
            self._file_controller.loaded.connect(self._blob_controller.set_source)
            self._file_controller.closed.connect(self._blob_controller.clear_source)
            self._blob_controller.params_changed.connect(
                lambda param, value: window.right_panel.notify_param_changed(
                    PipelineStep.DETECTION, param, value
                )
            )

            if preproc_sec := self.pipeline_controller.view.get_section(PipelineStep.PREPROCESSING):
                preproc_sec = cast(PreprocessingSection, preproc_sec)
                self._blob_controller.on_normalization_toggled(preproc_sec.normalization_enabled.isChecked())
                preproc_sec.normalization_toggled.connect(self._blob_controller.on_normalization_toggled)

            self._seed_histogram_controller = SeedHistogramController(
                window.left_panel.histograms_section.seed_response_histogram,
                detection_inspector,
                self._blob_controller,
                parent=self,
            )

        self._appearance_controller = (
            AppearanceController(window.left_panel, view, self._theme_controller.theme, self)
            if view is not None
            else None
        )
        if self._appearance_controller is not None:
            self._theme_controller.theme_changed.connect(self._appearance_controller.set_theme)

        window.left_panel.theme_switch_requested.connect(self._theme_controller.toggle)
        self._theme_controller.theme_changed.connect(window.right_panel.set_theme)
        window.right_panel.set_theme(self._theme_controller.theme)
        self._theme_controller.theme_changed.connect(window.left_panel.set_theme)
        window.left_panel.set_theme(self._theme_controller.theme)

        self._trajectory_controller: TrajectoryController | None = (
            TrajectoryController(window.left_panel, view, parent=self) if view is not None else None
        )
        if self._trajectory_controller is not None:
            self._playback_controller.frame_changed.connect(self._trajectory_controller.on_set_frame)
            self._file_controller.loaded.connect(self._trajectory_controller.clear_source)
            self._file_controller.closed.connect(self._trajectory_controller.clear_source)

        self._roi_view: RoiSelectionView | None = view if isinstance(view, RoiSelectionView) else None
        self._full_volume_bounds: Bounds6D | None = None
        self._roi_history: list[RegionOfInterest | None] = []
        self._connect_roi_workflow()
        self._batch_controller = BatchController(
            window,
            self.file_controller,
            self.pipeline_controller,
            self,
        )
        self._video_export_controller = VideoExportController(
            playback=self._playback_controller,
            view=view,
            volume=self._volume_controller,
            files=self._file_controller,
            parent=self,
        )

        self._has_precomputed_session = False
        # Connected after child controllers so source/blob/trajectory resets happen before session hydration
        self._file_controller.loaded.connect(self._on_file_loaded)
        self._file_controller.closed.connect(self._on_file_closed)

    @property
    def file_controller(self) -> FileController:
        """Controller of the opening of files."""
        return self._file_controller

    @property
    def playback_controller(self) -> PlaybackController:
        """Controller of the playback bar."""
        return self._playback_controller

    @property
    def theme_controller(self) -> ThemeController:
        """Controller of the theme."""
        return self._theme_controller

    @property
    def volume_controller(self) -> VolumeController | None:
        """Controller of the 3D view, None if the application has no 3D view."""
        return self._volume_controller

    @property
    def appearance_controller(self) -> AppearanceController | None:
        """Controller of the look of the 3D view, None if the application has no 3D view."""
        return self._appearance_controller

    @property
    def pipeline_model(self) -> PipelineModel:
        """Model representing the analysis pipeline state."""
        return self._pipeline_model

    @property
    def pipeline_controller(self) -> PipelineController:
        """Controller of the analysis pipeline."""
        return self._pipeline_controller

    @property
    def histogram_controller(self) -> HistogramController:
        """Controller of the intensity histograms."""
        return self._histogram_controller

    @property
    def tracking_result(self) -> TrackingResult | None:
        """Return the latest accepted tracking result."""
        return self._tracking_result

    def _detection_params(
        self,
    ) -> tuple[PreprocParams, BlobParams, RegionOfInterest | None]:
        """Take a snapshot of the sequence detection parameters."""
        roi = self._volume_controller.roi if self._volume_controller is not None else None

        if self._volume_controller is None:
            roi_dict = self._pipeline_model.get_step_params(PipelineStep.ROI)
            roi = RegionOfInterest.from_dict(roi_dict) if roi_dict else None

        return (
            self._pipeline_model.get_preproc_params(),
            BlobParams.from_dict(self._pipeline_model.get_step_params(PipelineStep.DETECTION)),
            roi,
        )

    def _on_detection_step_status_changed(
        self,
        step: PipelineStep,
        status: StepStatus,
    ) -> None:
        if step != PipelineStep.DETECTION:
            return

        if status == StepStatus.RUNNING:
            self._start_detection_if_needed()
        else:
            self._detection_generation += 1

    def _on_detection_pipeline_reset(self) -> None:
        self._detection_generation += 1

    def _start_detection_if_needed(self) -> None:
        """Compute detections using the already-open CZI source."""
        if (
            self._pipeline_model.get_status(PipelineStep.DETECTION) != StepStatus.RUNNING
            or self._detection_task is not None
        ):
            return

        # Reuse detections already stored in the pipeline.
        if self._pipeline_model.batch_results is not None:
            self._pipeline_controller.complete_stage(PipelineStep.DETECTION)
            return

        try:
            source = self._file_controller.source

            if source is None:
                raise ValueError("Open a CZI file before running detection.")

            params = self._detection_params()

            self._detection_running_source = source
            self._detection_running_params = params
            self._detection_running_generation = self._detection_generation

            preproc, blob, roi = params

            self._detection_task = self._detection_runner.run(
                partial(
                    detect_sequence,
                    cast(CziSource, source),
                    preproc,
                    blob,
                    roi,
                )
            )

        except Exception as error:
            self._report_detection_failure(error)

    def _detection_result_is_current(self) -> bool:
        return (
            self._detection_running_generation == self._detection_generation
            and self._pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.RUNNING
            and self._file_controller.source is self._detection_running_source
            and self._detection_running_params == self._detection_params()
        )

    def _on_detection_ready(
        self,
        task_id: int,
        result: object,
    ) -> None:
        if task_id != self._detection_task:
            return

        self._detection_task = None

        if not self._detection_result_is_current():
            self._start_detection_if_needed()
            return

        if not isinstance(result, DetectionData):
            self._report_detection_failure(TypeError("Detection returned an unexpected result."))
            return

        self._pipeline_model.set_batch_results(
            result.detections,
            result.metadata,
        )

        self._pipeline_controller.complete_stage(PipelineStep.DETECTION)

    def _on_detection_failed(
        self,
        task_id: int,
        error: object,
    ) -> None:
        if task_id != self._detection_task:
            return

        self._detection_task = None

        if not self._detection_result_is_current():
            self._start_detection_if_needed()
            return

        self._report_detection_failure(error)

    def _report_detection_failure(self, error: object) -> None:
        self._pipeline_model.invalidate_from(PipelineStep.DETECTION)

        reason = str(error) or type(error).__name__

        self._pipeline_controller.report_stage_failure(
            "Blob detection failed",
            reason,
        )

    @property
    def trajectory_controller(self) -> TrajectoryController | None:
        """Controller of 3D trajectory visualization, None if the application has no 3D view."""
        return self._trajectory_controller

    def open_mock(self, config: MockConfig | None = None) -> None:
        """Open a synthetic mock recording in the background."""
        self._file_controller.open_with(
            Path(texts.MOCK_SOURCE_NAME),
            lambda: create_mock_source(config),
        )

    def apply_precomputed_session(self, session: PrecomputedSession, dt_s: float | None = None) -> None:
        """Hydrate pipeline stages, precomputed blobs, and trajectories from `session`."""
        self._has_precomputed_session = True
        self._pipeline_model.reset_all()
        self._apply_session_params(session)

        completed = set(infer_completed_steps(session))
        for step in PIPELINE_STEP_ORDER:
            if step.value not in completed:
                break
            self._pipeline_model.set_step_status(step, StepStatus.COMPLETED)

        blobs_df = session.effective_blobs
        if self._blob_controller is not None:
            self._blob_controller.set_precomputed_blobs(blobs_df)

        self._tracking_result = session.tracking
        if self._trajectory_controller is not None:
            if session.tracking is not None:
                effective_dt = dt_s
                if effective_dt is None and self._file_controller.source is not None:
                    effective_dt = self._file_controller.source.info.dt_s
                self._trajectory_controller.set_trajectories(
                    session.tracking.tracks,
                    dt_s=effective_dt,
                    current_frame=self._playback_controller.frame,
                )
            else:
                self._trajectory_controller.clear_source()

    def _apply_session_params(self, session: PrecomputedSession) -> None:
        if session.roi is not None:
            self._pipeline_model.update_step_params(PipelineStep.ROI, **session.roi.to_dict())
        if session.preproc_params is not None:
            self._pipeline_model.update_step_params(
                PipelineStep.PREPROCESSING, **session.preproc_params.to_dict()
            )
        if session.blob_params is not None:
            self._pipeline_model.update_step_params(PipelineStep.DETECTION, **session.blob_params.to_dict())
        if session.tracking_config is not None:
            self._pipeline_model.update_step_params(
                PipelineStep.TRACKING, **session.tracking_config.model_dump()
            )

    def _clear_precomputed_session(self) -> None:
        self._has_precomputed_session = False
        self._tracking_result = None
        self._pipeline_model.reset_all()

    def _on_tracking_step_status_changed(self, step: PipelineStep, status: StepStatus) -> None:
        """Start tracking and invalidate outdated results."""
        if step != PipelineStep.TRACKING:
            return

        if status != StepStatus.COMPLETED:
            self._tracking_result = None
            if self._trajectory_controller is not None:
                self._trajectory_controller.clear_source()

        if status == StepStatus.RUNNING:
            self._start_tracking_if_needed()
        else:
            self._tracking_generation += 1

    def _on_tracking_pipeline_reset(self) -> None:
        """Invalidate results from previous tracking runs."""
        self._tracking_generation += 1
        self._tracking_result = None
        if self._trajectory_controller is not None:
            self._trajectory_controller.clear_source()

    def _start_tracking_if_needed(self) -> None:
        """Link only detections stored by the detection stage."""
        if self._pipeline_model.get_status(PipelineStep.TRACKING) != StepStatus.RUNNING:
            return

        if self._tracking_controller.is_running:
            return

        config = TrackingConfig(**self._pipeline_model.get_step_params(PipelineStep.TRACKING))

        batch_results = self._pipeline_model.batch_results

        if batch_results is None:
            self._tracking_running_config = config
            self._tracking_running_generation = self._tracking_generation

            self._on_tracking_failed(ValueError("No detections available. Run the Detection stage first."))
            return

        detections, metadata = batch_results
        dt_s = metadata.get("info", {}).get("dt_s")

        self._tracking_running_config = config
        self._tracking_running_generation = self._tracking_generation

        try:
            self._tracking_controller.run(
                detections,
                config,
                dt_s=dt_s,
            )
        except Exception as error:
            self._on_tracking_failed(error)

    def _tracking_result_is_current(self) -> bool:
        """Check whether the completed task still matches the pipeline."""
        if self._tracking_running_generation != self._tracking_generation:
            return False

        if self._pipeline_model.get_status(PipelineStep.TRACKING) != StepStatus.RUNNING:
            return False

        current_config = TrackingConfig(**self._pipeline_model.get_step_params(PipelineStep.TRACKING))
        return current_config == self._tracking_running_config

    def _on_tracking_ready(self, result: TrackingResult) -> None:
        """Accept the result only when the running configuration is current."""
        if not self._tracking_result_is_current():
            self._start_tracking_if_needed()
            return

        self._tracking_result = result
        if self._trajectory_controller is not None:
            dt_s = (
                self._file_controller.source.info.dt_s if self._file_controller.source is not None else None
            )
            self._trajectory_controller.set_trajectories(
                result.tracks,
                dt_s=dt_s,
                current_frame=self._playback_controller.frame,
            )
        self._pipeline_controller.complete_stage(PipelineStep.TRACKING)

    def _on_tracking_failed(self, error: Exception) -> None:
        """Report failures and restore the pipeline to a retryable state."""
        if not self._tracking_result_is_current():
            self._start_tracking_if_needed()
            return

        self._tracking_result = None
        self._pipeline_model.invalidate_from(PipelineStep.TRACKING)

        reason = str(error) or type(error).__name__
        self._window.right_panel.set_stats_summary("Trajectory linking failed")
        self._window.right_panel.set_stats_details(reason)
        self._pipeline_controller.report_stage_failure("Trajectory linking failed", reason)

    def _on_file_loaded(self, _path: Path, source: FrameSource) -> None:
        playback = self._playback_controller
        playback.set_playing(False)
        playback.set_frame_count(source.info.n_t)
        playback.go_to_frame(0)

        if isinstance(source, PrecomputedSource):
            self.apply_precomputed_session(source.session, dt_s=source.info.dt_s)
        elif self._has_precomputed_session:
            self._clear_precomputed_session()

        self._window.playback_bar.setEnabled(True)

    def _on_file_closed(self) -> None:
        if self._has_precomputed_session:
            self._clear_precomputed_session()

    def _on_volume_failed(self) -> None:
        self._playback_controller.set_playing(False)  # otherwise every frame would report the same error

    def _connect_roi_workflow(self) -> None:
        """Connect the RoiInspector in the RightPanel with the Viewport and VolumeController."""
        inspector = self._window.right_panel.roi_inspector
        if inspector is None:
            return

        if self._volume_controller is not None:
            self._volume_controller.volume_bounds_changed.connect(self._on_volume_bounds_changed)

        # conntect the RoiInspector buttons to the MainController, which will orchestrate the workflow
        inspector.select_roi_clicked.connect(self._on_start_roi_selection)
        inspector.accept_roi_clicked.connect(self._on_accept_roi)
        inspector.cancel_roi_clicked.connect(self._on_cancel_roi)
        inspector.reset_roi_clicked.connect(self._on_reset_roi)
        inspector.bounds_edited.connect(self._on_inspector_bounds_edited)
        inspector.undo_roi_clicked.connect(self._on_undo_roi)

        # Connect Viewport ROI signals if the 3D view supports interactive ROI selection
        if self._roi_view is not None:
            self._roi_view.roi_updated.connect(self._on_viewport_roi_updated)

    def _on_volume_bounds_changed(self, bounds: Bounds6D) -> None:
        """
        Update the RoiInspector with the new bounds of the volume
        Parameters:
            bounds: The new bounds of the volume.

        Returns:
            None
        """
        self._full_volume_bounds = bounds
        self._roi_history.clear()
        inspector = self._window.right_panel.roi_inspector
        if inspector is not None:
            inspector.set_volume_bounds(bounds)
            inspector.set_editing_mode(False)
            inspector.set_undo_enabled(False)
            inspector.set_status_text(texts.INSPECTOR_STATUS_ROI_FULL)

    def _pause_and_lock_playback_for_roi(self) -> None:
        """Pause playback and disable the playback bar while the user is selecting/editing a ROI."""
        self._playback_controller.set_playing(False)
        self._window.playback_bar.setEnabled(False)

    def _unlock_playback_after_roi(self) -> None:
        """Re-enable the playback bar if a recording is currently open."""
        if self._file_controller.source is not None:
            self._window.playback_bar.setEnabled(True)

    def _on_start_roi_selection(self) -> None:
        """Start the interactive ROI selection workflow.
        This is called when the user clicks the "Select ROI" button in the RoiInspector.
        """
        if self._file_controller.source is None:
            return

        self._pause_and_lock_playback_for_roi()

        inspector = self._window.right_panel.roi_inspector
        if inspector is not None:
            if self._volume_controller is not None and self._volume_controller.roi is not None:
                inspector.set_volume_bounds(self._volume_controller.roi.bounds)
            inspector.set_editing_mode(True)

        if self._roi_view is not None:
            self._roi_view.start_roi_selection()

    def _on_viewport_roi_updated(self, roi: RegionOfInterest) -> None:
        """Update the RoiInspector with the new ROI bounds from the viewport.
        This is called when the user finishes selecting an ROI in the 3D view.
        Parameters:
            roi: The new RegionOfInterest.
        Returns:
            None
        """
        inspector = self._window.right_panel.roi_inspector
        if inspector is not None:
            inspector.set_roi_bounds(roi.bounds)
            inspector.set_editing_mode(True)

    def _on_inspector_bounds_edited(self, roi: RegionOfInterest) -> None:
        if self._file_controller.source is None:
            return

        self._pause_and_lock_playback_for_roi()

        if self._volume_controller is not None and self._volume_controller.roi is not None:
            self._volume_controller.set_roi(None)

        if self._roi_view is not None:
            self._roi_view.set_roi_preview(roi)

    def _on_accept_roi(self) -> None:
        """Accept the current ROI.
        This is called when the user clicks the "Accept" button in the RoiInspector.
        Returns:
            None
        """
        inspector = self._window.right_panel.roi_inspector
        if inspector is None:
            return

        roi: RegionOfInterest | None = None
        if self._roi_view is not None:
            roi = self._roi_view.accept_roi_selection()

        if roi is None:
            roi = inspector.get_roi()

        if self._volume_controller is not None:
            # here i store the prev roi for the undo thing
            prev_roi = self._volume_controller.roi
            if prev_roi != roi:
                self._roi_history.append(prev_roi)
            self._volume_controller.set_roi(roi)

        inspector.set_roi_bounds(roi.bounds)
        inspector.set_editing_mode(False)
        inspector.set_undo_enabled(len(self._roi_history) > 0)
        x0, x1, y0, y1, z0, z1 = roi.bounds
        inspector.set_status_text(
            texts.INSPECTOR_STATUS_ROI_ACTIVE.format(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)
        )

        self._pipeline_model.update_step_params(PipelineStep.ROI, **roi.to_dict())
        self._pipeline_controller.complete_stage(PipelineStep.ROI)
        self._unlock_playback_after_roi()

    def _on_cancel_roi(self) -> None:
        """Cancel the current ROI selection.
        This is called when the user clicks the "Cancel" button in the RoiInspector.
        Returns:
            None
        """
        if self._roi_view is not None:
            self._roi_view.cancel_roi_selection()

        inspector = self._window.right_panel.roi_inspector
        if inspector is not None:
            inspector.set_editing_mode(False)
            active_roi = self._volume_controller.roi if self._volume_controller is not None else None
            if active_roi is not None:
                inspector.set_roi_bounds(active_roi.bounds)
                x0, x1, y0, y1, z0, z1 = active_roi.bounds
                inspector.set_status_text(
                    texts.INSPECTOR_STATUS_ROI_ACTIVE.format(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)
                )
            elif self._full_volume_bounds is not None:
                inspector.set_roi_bounds(self._full_volume_bounds)
                inspector.set_status_text(texts.INSPECTOR_STATUS_ROI_FULL)

        self._unlock_playback_after_roi()

    def _on_reset_roi(self) -> None:
        """Reset the ROI to the full volume.
        This is called when the user clicks the "Reset" button in the RoiInspector.
        Returns:
            None
        """
        if self._roi_view is not None:
            self._roi_view.cancel_roi_selection()

        if self._volume_controller is not None:
            self._volume_controller.set_roi(None)

        self._roi_history.clear()
        inspector = self._window.right_panel.roi_inspector
        if inspector is not None:
            inspector.set_editing_mode(False)
            inspector.set_undo_enabled(False)
            if self._full_volume_bounds is not None:
                inspector.set_roi_bounds(self._full_volume_bounds)
            inspector.set_status_text(texts.INSPECTOR_STATUS_ROI_FULL)

        self._unlock_playback_after_roi()

    def _on_undo_roi(self) -> None:
        """Revert to the previous accepted ROI (or to the full volume if undoing the first crop)."""
        if not self._roi_history:
            return

        # If the user is currently selecting or editing a ROI, cancel that operation first
        if self._roi_view is not None:
            self._roi_view.cancel_roi_selection()

        prev_roi = self._roi_history.pop()

        if self._volume_controller is not None:
            # if prev roi is None set roi will reset to full volume
            self._volume_controller.set_roi(prev_roi)

        inspector = self._window.right_panel.roi_inspector
        if inspector is not None:
            inspector.set_editing_mode(False)
            inspector.set_undo_enabled(len(self._roi_history) > 0)

            if prev_roi is not None:
                # update the spinboxes with new bounds
                inspector.set_volume_bounds(prev_roi.bounds)
                x0, x1, y0, y1, z0, z1 = prev_roi.bounds
                inspector.set_status_text(
                    texts.INSPECTOR_STATUS_ROI_ACTIVE.format(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)
                )
                self._pipeline_model.update_step_params(PipelineStep.ROI, **prev_roi.to_dict())
            else:
                # if prev roi is None, reset to full volume so the bounds of the
                # spinboxes are updated to the full volume bounds
                if self._full_volume_bounds is not None:
                    inspector.set_volume_bounds(self._full_volume_bounds)
                inspector.set_status_text(texts.INSPECTOR_STATUS_ROI_FULL)

        self._unlock_playback_after_roi()

    def _on_step_params_changed(self, step: PipelineStep) -> None:
        if self._volume_controller is not None and step == PipelineStep.PREPROCESSING:
            self._volume_controller.apply_preproc_params(self.pipeline_model.get_preproc_params())

    def _on_suggest_window_clicked(self) -> None:
        if self._volume_controller is not None:
            self._volume_controller.suggest_intensity_window()

    def _on_window_suggested(self, lo: float, hi: float) -> None:
        if preproc_sec := self.pipeline_controller.view.get_section(PipelineStep.PREPROCESSING):
            cast(PreprocessingSection, preproc_sec).set_intensity_window(lo, hi)
