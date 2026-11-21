"""
Controller of the main window.

It is the only place where the view meets the rest of the application. It creates the other controllers
and connects them: the `FileController` opens the files, the `PlaybackController` moves through the
frames, the `VolumeController` shows them in the 3D view, the `AppearanceController` changes how the
3D view looks, the `ThemeController` changes the look of the application, and the `PipelineController`
orchestrates the analysis pipeline.
"""

from pathlib import Path
from typing import Protocol, cast

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.appearance_controller import AppearanceController, AppearanceView
from apkit4d.gui.controllers.batch_controller import BatchController
from apkit4d.gui.controllers.blob_detection_controller import BlobDetectionController, BlobView
from apkit4d.gui.controllers.file_controller import FileController, FrameSource, SourceOpener
from apkit4d.gui.controllers.histogram_controller import HistogramController
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.roi_controller import RoiStageController
from apkit4d.gui.controllers.seed_histogram_controller import SeedHistogramController
from apkit4d.gui.controllers.theme_controller import ThemeController
from apkit4d.gui.controllers.trajectory_controller import TrajectoryController, TrajectoryView
from apkit4d.gui.controllers.trajectory_linking_controller import (
    TrajectoryLinkingController,
)
from apkit4d.gui.controllers.video_export_controller import (
    VideoExportController,
    VideoExportView,
)
from apkit4d.gui.controllers.volume_controller import VolumeController, VolumeView
from apkit4d.gui.models.pipeline_model import (
    PIPELINE_STEP_ORDER,
    PipelineModel,
    PipelineStep,
    StepStatus,
)
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.stages.preprocessing_section import PreprocessingSection
from apkit4d.gui.views.widgets.dialogs.video_export_dialog import VideoExportDialog
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
        if detection_inspector := window.right_panel.detection_inspector:
            self._blob_controller = BlobDetectionController(
                detection_inspector,
                view,
                parent=self,
                pipeline_model=self._pipeline_model,
                pipeline_controller=self._pipeline_controller,
                file_controller=self._file_controller,
                volume_controller=self._volume_controller,
            )
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

            if view is not None and self._volume_controller is not None:
                self._volume_controller.volume_prepared.connect(self._blob_controller.on_volume_prepared)
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

        self._tracking_controller = TrajectoryLinkingController(
            self,
            pipeline_model=self._pipeline_model,
            pipeline_controller=self._pipeline_controller,
            file_controller=self._file_controller,
            trajectory_controller=self._trajectory_controller,
            playback_controller=self._playback_controller,
        )

        self._roi_controller = RoiStageController(
            inspector=window.right_panel.roi_inspector,
            volume_controller=self._volume_controller,
            pipeline_model=self._pipeline_model,
            pipeline_controller=self._pipeline_controller,
            playback_controller=self._playback_controller,
            file_controller=self._file_controller,
            playback_bar=window.playback_bar,
            view=view,
            parent=self,
        )
        self._batch_controller = BatchController(
            window,
            self.file_controller,
            self.pipeline_controller,
            self,
        )
        self._video_export_controller = VideoExportController(
            playback_controller=self._playback_controller,
            view=view,
            volume_controller=self._volume_controller,
            file_controller=self._file_controller,
            parent=self,
        )
        window.video_export_requested.connect(self._show_video_export_dialog)

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
    def roi_controller(self) -> RoiStageController:
        """Controller managing the Stage 1 Region of Interest workflow."""
        return self._roi_controller

    @property
    def blob_controller(self) -> BlobDetectionController | None:
        """Controller managing single-frame and Stage 3 blob detection."""
        return self._blob_controller

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
        return self._tracking_controller.result

    def _show_video_export_dialog(self) -> None:
        dialog = VideoExportDialog(self._video_export_controller, self._window)
        dialog.exec()

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

        effective_dt = dt_s
        if effective_dt is None and self._file_controller.source is not None:
            effective_dt = self._file_controller.source.info.dt_s
        self._tracking_controller.set_precomputed_result(
            session.tracking,
            dt_s=effective_dt,
            current_frame=self._playback_controller.frame,
        )

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
        self._tracking_controller.clear_result()
        self._pipeline_model.reset_all()

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

    def _on_step_params_changed(self, step: PipelineStep) -> None:
        if self._volume_controller is not None and step == PipelineStep.PREPROCESSING:
            self._volume_controller.apply_preproc_params(self.pipeline_model.get_preproc_params())

    def _on_suggest_window_clicked(self) -> None:
        if self._volume_controller is not None:
            self._volume_controller.suggest_intensity_window()

    def _on_window_suggested(self, lo: float, hi: float) -> None:
        if preproc_sec := self.pipeline_controller.view.get_section(PipelineStep.PREPROCESSING):
            cast(PreprocessingSection, preproc_sec).set_intensity_window(lo, hi)
