"""Controller orchestrating the Stage 1 Region of Interest (ROI) workflow."""

import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from apkit4d.core.frame_range import FrameRange
from apkit4d.core.roi import Bounds6D, RegionOfInterest
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.volume_controller import RoiSelectionView, VolumeController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.playback.playback_bar import PlaybackBar
from apkit4d.gui.views.stages.roi_inspector import RoiInspector
from apkit4d.visualization.viewport import RoiMode

logger = logging.getLogger(__name__)


class RoiStageController(QObject):
    """Coordinates ROI selection, preview, undo history, and Stage 1 model state."""

    roi_interaction_started = Signal()

    def __init__(
        self,
        inspector: RoiInspector | None,
        volume_controller: VolumeController | None,
        pipeline_model: PipelineModel,
        pipeline_controller: PipelineController,
        playback_controller: PlaybackController,
        file_controller: FileController,
        playback_bar: PlaybackBar | None = None,
        view: object | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._inspector = inspector
        self._volume_controller = volume_controller
        self._pipeline_model = pipeline_model
        self._pipeline_controller = pipeline_controller
        self._playback_controller = playback_controller
        self._file_controller = file_controller
        self._playback_bar = playback_bar
        self._roi_view: RoiSelectionView | None = view if isinstance(view, RoiSelectionView) else None

        self._full_volume_bounds: Bounds6D | None = None
        self._roi_history: list[RegionOfInterest | None] = []

        self._connect_signals()
        self._pipeline_controller.set_stage_runner(PipelineStep.ROI, self.commit_active_roi)

    def commit_active_roi(self) -> None:
        """Auto-commit the active ROI (or full uncropped volume) and complete Stage 1."""
        if self._roi_view is not None:
            self._roi_view.accept_roi_selection()

        if self._volume_controller is not None:
            active_roi = self._volume_controller.roi
            if active_roi is not None:
                self._pipeline_model.set_roi_params(
                    self._pipeline_model.get_roi_params().with_region(active_roi)
                )
            elif self._pipeline_model.get_roi_params().region is None:
                self._pipeline_model.set_roi_params(self._pipeline_model.get_roi_params().with_region(None))

        self._unlock_playback_after_roi()
        self._pipeline_controller.complete_stage(PipelineStep.ROI)
        logger.debug("Committed active ROI and completed Stage 1")

    def show_roi(self, roi: RegionOfInterest) -> None:
        """
        Show `roi` as the accepted ROI: the volume is cropped to it and the inspector shows its bounds.

        Used for the ROI of saved results, whose parameters and stage status are restored by the caller.
        """
        self._roi_history.clear()
        if self._volume_controller is not None:
            self._volume_controller.set_roi(roi)
        self._apply_roi_to_inspector(roi)

    def cancel_active_roi_editing(self) -> None:
        """Cancel an active DATA_ROI selection/preview if one is currently in progress."""
        view_active = getattr(self._roi_view, "roi_mode", RoiMode.INACTIVE) != RoiMode.INACTIVE
        inspector_active = self._inspector is not None and self._inspector._editing_mode
        if not view_active and not inspector_active:
            return
        self._on_cancel_roi()

    @property
    def full_volume_bounds(self) -> Bounds6D | None:
        """Full uncropped physical bounds of the active recording, if known."""
        return self._full_volume_bounds

    @property
    def has_undo(self) -> bool:
        """Whether there is a previous ROI state available to restore."""
        return bool(self._roi_history)

    def _connect_signals(self) -> None:
        if self._inspector is None:
            return

        self._file_controller.loaded.connect(self._on_source_loaded)
        self._file_controller.closed.connect(self._on_source_closed)

        if self._volume_controller is not None:
            self._volume_controller.volume_bounds_changed.connect(self._on_volume_bounds_changed)

        self._inspector.select_roi_clicked.connect(self._on_start_roi_selection)
        self._inspector.accept_roi_clicked.connect(self._on_accept_roi)
        self._inspector.cancel_roi_clicked.connect(self._on_cancel_roi)
        self._inspector.reset_roi_clicked.connect(self._on_reset_roi)
        self._inspector.bounds_edited.connect(self._on_inspector_bounds_edited)
        self._inspector.undo_roi_clicked.connect(self._on_undo_roi)
        self._inspector.selected_frames_confirmed.connect(self._on_selected_frames_confirmed)

        if self._roi_view is not None:
            self._roi_view.roi_updated.connect(self._on_viewport_roi_updated)

    def _on_selected_frames_confirmed(self, frame_range: FrameRange | None):
        roi_params = self._pipeline_model.get_roi_params()

        self._pipeline_model.set_roi_params(roi_params.with_frame_range(frame_range))
        self._playback_controller.set_frame_range(frame_range)

        if roi_params.frame_range is not None and frame_range is not None:
            if not roi_params.frame_range.contains(frame_range):
                self._pipeline_model.invalidate_from(PipelineStep.ROI)
        elif roi_params.frame_range != frame_range:
            self._pipeline_model.invalidate_from(PipelineStep.ROI)

    def _on_volume_bounds_changed(self, bounds: Bounds6D) -> None:
        """Initialize ROI bounds and clear undo history when a new recording loads."""
        self._full_volume_bounds = bounds
        self._roi_history.clear()
        if self._inspector is not None:
            self._inspector.set_volume_bounds(bounds)
            self._inspector.set_editing_mode(False)
            self._inspector.set_undo_enabled(False)
            self._inspector.set_status_text(texts.INSPECTOR_STATUS_ROI_FULL)

    def _pause_and_lock_playback_for_roi(self) -> None:
        """Pause playback and disable the playback bar while editing an ROI."""
        self._playback_controller.set_playing(False)
        if self._playback_bar is not None:
            self._playback_bar.setEnabled(False)

    def _unlock_playback_after_roi(self) -> None:
        """Re-enable the playback bar if a recording is currently open."""
        if self._playback_bar is not None and self._file_controller.source is not None:
            self._playback_bar.setEnabled(True)

    def _on_start_roi_selection(self) -> None:
        """Start interactive 3D ROI selection."""
        if self._file_controller.source is None:
            return

        self.roi_interaction_started.emit()
        self._pause_and_lock_playback_for_roi()

        if self._inspector is not None:
            if self._volume_controller is not None and self._volume_controller.roi is not None:
                self._inspector.set_volume_bounds(self._volume_controller.roi.bounds)
            self._inspector.set_editing_mode(True)

        if self._roi_view is not None:
            self._roi_view.start_roi_selection()

    def _on_viewport_roi_updated(self, roi: RegionOfInterest) -> None:
        """Sync inspector spinboxes when the 3D viewport preview box changes."""
        if self._inspector is not None:
            self._inspector.set_roi_bounds(roi.bounds)
            self._inspector.set_editing_mode(True)

    def _on_inspector_bounds_edited(self, roi: RegionOfInterest) -> None:
        """Preview manually edited ROI bounds without mutating the accepted ROI."""
        if self._file_controller.source is None:
            return

        self.roi_interaction_started.emit()
        self._pause_and_lock_playback_for_roi()

        if self._roi_view is not None:
            self._roi_view.set_roi_preview(roi)

    def _on_accept_roi(self) -> None:
        """Commit the edited/selected ROI to VolumeController and PipelineModel."""
        if self._inspector is None:
            return

        roi: RegionOfInterest | None = None
        if self._roi_view is not None:
            roi = self._roi_view.accept_roi_selection()

        if roi is None:
            roi = self._inspector.get_roi()

        if self._volume_controller is not None:
            prev_roi = self._volume_controller.roi
            if prev_roi != roi:
                self._roi_history.append(prev_roi)
            self._volume_controller.set_roi(roi)

        self._apply_roi_to_inspector(roi)
        self._pipeline_model.set_roi_params(self._pipeline_model.get_roi_params().with_region(roi))

        self._pipeline_controller.complete_stage(PipelineStep.ROI)
        self._unlock_playback_after_roi()
        logger.debug("Accepted ROI bounds: %s", roi.bounds)

    def _on_cancel_roi(self) -> None:
        """Discard the active preview and restore the previously accepted ROI."""
        if self._roi_view is not None:
            self._roi_view.cancel_roi_selection()

        active_roi = self._volume_controller.roi if self._volume_controller is not None else None
        self._restore_inspector_to_roi(active_roi)
        self._unlock_playback_after_roi()
        logger.debug("Cancelled ROI edit; restored active ROI=%s", active_roi)

    def _on_reset_roi(self) -> None:
        """Reset ROI to the full volume and synchronize PipelineModel."""
        if self._roi_view is not None:
            self._roi_view.cancel_roi_selection()

        if self._volume_controller is not None:
            self._volume_controller.set_roi(None)

        self._roi_history.clear()
        self._restore_inspector_to_roi(None)
        self._reset_frame_range_to_full()
        self._sync_model_reset_region_to_full()
        self._unlock_playback_after_roi()
        logger.debug("Reset ROI to full volume and invalidated downstream stages")

    def _on_undo_roi(self) -> None:
        """Revert to the previous accepted ROI (or full volume on initial crop undo)."""
        if not self._roi_history:
            return

        if self._roi_view is not None:
            self._roi_view.cancel_roi_selection()

        prev_roi = self._roi_history.pop()

        if self._volume_controller is not None:
            self._volume_controller.set_roi(prev_roi)

        self._restore_inspector_to_roi(prev_roi)
        if prev_roi is not None:
            self._pipeline_model.set_roi_params(self._pipeline_model.get_roi_params().with_region(prev_roi))
            self._pipeline_model.invalidate_subsequent(PipelineStep.ROI)
        else:
            self._sync_model_reset_region_to_full()

        self._unlock_playback_after_roi()
        logger.debug("Undid ROI change; restored prev_roi=%s", prev_roi)

    def _reset_frame_range_to_full(self) -> None:
        source = self._file_controller.source

        if self._inspector is not None and source is not None:
            self._inspector.frames_selector.set_frame_range(FrameRange.full(source.info.n_t), True)

        roi_params = self._pipeline_model.get_roi_params()
        self._pipeline_model.set_roi_params(roi_params.with_frame_range(None))

        if roi_params.frame_range is not None:  # they are the previous params because the class is freezed
            self._pipeline_model.invalidate_from(PipelineStep.ROI)

    def _sync_model_reset_region_to_full(self) -> None:
        """Reset ROI parameters in PipelineModel and invalidate ROI and downstream stages."""
        self._pipeline_model.set_roi_params(self._pipeline_model.get_roi_params().with_region(None))
        self._pipeline_model.invalidate_from(PipelineStep.ROI)

    def _apply_roi_to_inspector(self, roi: RegionOfInterest) -> None:
        if self._inspector is None:
            return
        self._inspector.set_roi_bounds(roi.bounds)
        self._inspector.set_editing_mode(False)
        self._inspector.set_undo_enabled(self.has_undo)
        x0, x1, y0, y1, z0, z1 = roi.bounds
        self._inspector.set_status_text(
            texts.INSPECTOR_STATUS_ROI_ACTIVE.format(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)
        )

    def _restore_inspector_to_roi(self, roi: RegionOfInterest | None) -> None:
        if self._inspector is None:
            return
        if self._full_volume_bounds is not None:
            self._inspector.set_volume_bounds(self._full_volume_bounds)

        self._inspector.set_editing_mode(False)
        self._inspector.set_undo_enabled(self.has_undo)

        if roi is not None:
            if self._full_volume_bounds is None:
                self._inspector.set_volume_bounds(roi.bounds)
            else:
                self._inspector.set_roi_bounds(roi.bounds)
            x0, x1, y0, y1, z0, z1 = roi.bounds
            self._inspector.set_status_text(
                texts.INSPECTOR_STATUS_ROI_ACTIVE.format(x0=x0, x1=x1, y0=y0, y1=y1, z0=z0, z1=z1)
            )
        else:
            if self._full_volume_bounds is not None:
                self._inspector.set_roi_bounds(self._full_volume_bounds)
            self._inspector.set_status_text(texts.INSPECTOR_STATUS_ROI_FULL)

    def _on_source_loaded(self, _path: Path, source: FrameSource) -> None:
        self._reset_frame_range_to_full()

    def _on_source_closed(self) -> None:
        self._pipeline_model.set_roi_params(self._pipeline_model.get_roi_params().with_frame_range(None))

        if inspector := self._inspector:
            inspector.frames_selector.set_frame_range(None, True)
