"""
Controller of the main window.

It is the only place where the view meets the rest of the application. It creates the other controllers
and connects them: the `FileController` opens the files, the `PlaybackController` moves through the
frames, the `VolumeController` shows them in the 3D view, the `ThemeController` changes the look of the
application, and the `PipelineController` orchestrates the analysis pipeline.
"""

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource, SourceOpener
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.theme_controller import ThemeController
from apkit4d.gui.controllers.volume_controller import RoiSelectionView, VolumeController, VolumeView
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziSource
from apkit4d.roi import Bounds6D, RegionOfInterest


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
        view: VolumeView | None = None,
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
        self._file_controller.loaded.connect(self._on_file_loaded)

        window.left_panel.theme_switch_requested.connect(self._theme_controller.toggle)
        self._theme_controller.theme_changed.connect(window.right_panel.set_theme)
        window.right_panel.set_theme(self._theme_controller.theme)
        self._theme_controller.theme_changed.connect(window.left_panel.set_theme)
        window.left_panel.set_theme(self._theme_controller.theme)
        # TODO: the 3D view does not follow the theme yet: it needs a method to change its background,
        # and then `self._theme_controller.theme_changed.connect(view.set_theme)`

        self._roi_view: RoiSelectionView | None = view if isinstance(view, RoiSelectionView) else None
        self._full_volume_bounds: Bounds6D | None = None
        self._roi_history: list[RegionOfInterest | None] = []
        self._connect_roi_workflow()

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
    def pipeline_model(self) -> PipelineModel:
        """Model representing the analysis pipeline state."""
        return self._pipeline_model

    @property
    def pipeline_controller(self) -> PipelineController:
        """Controller of the analysis pipeline."""
        return self._pipeline_controller

    def _on_file_loaded(self, _path: Path, source: FrameSource) -> None:
        playback = self._playback_controller
        playback.set_playing(False)
        playback.set_frame_count(source.info.n_t)
        playback.go_to_frame(0)
        self._window.playback_bar.setEnabled(True)

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
