"""Controller coordinating the Visualization Sub-ROI workflow across UI, Viewport, and pipeline."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from PySide6.QtCore import QObject, Signal

from apkit4d.core.roi import Bounds6D
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.models.pipeline_model import PIPELINE_STEP_ORDER, PipelineModel, PipelineStep, StepStatus
from apkit4d.visualization.vis_sub_roi import (
    DEFAULT_OUTSIDE_OPACITY,
    VisSubRoiState,
    clamp_outside_opacity,
)


class _SignalLike(Protocol):
    def connect(self, slot: Callable[..., object]) -> object: ...


@runtime_checkable
class VisSubRoiView(Protocol):
    """Rendering and interactive 3D box contract provided by `Viewport`.
    we define all we need from the viewport
    """

    @property
    def vis_sub_roi_state(self) -> VisSubRoiState: ...

    @property
    def displayed_volume_bounds_updated(self) -> _SignalLike: ...

    @property
    def vis_sub_roi_selection_started(self) -> _SignalLike: ...

    @property
    def vis_sub_roi_bounds_changed(self) -> _SignalLike: ...

    @property
    def vis_sub_roi_interaction_ended(self) -> _SignalLike: ...

    def set_vis_sub_roi_state(self, state: VisSubRoiState) -> None: ...

    def set_vis_sub_roi_enabled(self, enabled: bool) -> None: ...

    def set_vis_sub_roi_bounds(self, bounds: Bounds6D | None) -> None: ...

    def set_vis_sub_roi_outside_opacity(self, outside_opacity: float) -> None: ...

    def clear_vis_sub_roi(self) -> None: ...

    def reset_vis_sub_roi_state(self) -> None: ...

    def start_vis_sub_roi_selection(self) -> None: ...

    def stop_vis_sub_roi_interaction(self) -> None: ...

    def show_vis_sub_roi_box(self, bounds: Bounds6D | None = None) -> None: ...

    def set_vis_sub_roi_box_visible(self, visible: bool, bounds: Bounds6D | None = None) -> None: ...


@runtime_checkable
class VisSubRoiSectionView(Protocol):
    """UI section contract provided by `VisSubRoiSection` in the left panel.
    we define all we need from the sub_roi section
    """

    @property
    def enabled_toggled(self) -> _SignalLike: ...

    @property
    def select_region_clicked(self) -> _SignalLike: ...

    @property
    def bounds_edited(self) -> _SignalLike: ...

    @property
    def outside_opacity_changed(self) -> _SignalLike: ...

    @property
    def reset_clicked(self) -> _SignalLike: ...

    @property
    def is_available(self) -> bool: ...

    @property
    def bounds(self) -> Bounds6D: ...

    def set_available(self, available: bool) -> None: ...

    def set_volume_bounds(self, bounds: Bounds6D) -> None: ...

    def set_sub_roi_bounds(self, bounds: Bounds6D | None) -> None: ...

    def set_sub_roi_enabled(self, enabled: bool) -> None: ...

    def set_outside_opacity(self, opacity: float) -> None: ...

    def set_state(self, state: VisSubRoiState) -> None: ...

    def set_status_text(self, text: str) -> None: ...


class VisSubRoiController(QObject):
    """Coordinates Visualization Sub-ROI availability, UI controls, and 3D Viewport state.

    Strictly display-only: never modifies scientific data, `VolumeController` DATA_ROI state,
    or `PipelineModel` step statuses/parameters.

    Signals:
        interaction_starting: Emitted right before starting 3D Sub-ROI selection so
            `MainController` can cancel any active DATA_ROI edit cleanly.
    """

    interaction_starting = Signal()

    def __init__(
        self,
        section: object | None,
        pipeline_model: PipelineModel,
        file_controller: FileController,
        view: object | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._section: VisSubRoiSectionView | None = (
            section if isinstance(section, VisSubRoiSectionView) else None
        )
        self._pipeline_model = pipeline_model
        self._file_controller = file_controller
        self._vis_view: VisSubRoiView | None = view if isinstance(view, VisSubRoiView) else None

        self._displayed_volume_bounds: Bounds6D | None = None
        # track the last state of availability to avoid unnecessary
        #  UI updates when the pipeline is dirty
        self._last_available: bool = False

        self._connect_signals()
        self._sync_availability(force_ui_sync=True)

    @property
    def displayed_volume_bounds(self) -> Bounds6D | None:
        """World-space bounds of the currently displayed volume grid, if known."""
        return self._displayed_volume_bounds

    @property
    def is_available(self) -> bool:
        """True only when the detection is complete and a display volume is available."""
        if self._vis_view is None or self._displayed_volume_bounds is None:
            return False
        # only available when the blobs are calculated
        if (
            self._pipeline_model.statuses.get(PipelineStep.DETECTION, StepStatus.COMPLETED)
            != StepStatus.COMPLETED
        ):
            return False
        return not any(self._pipeline_model.is_step_dirty(step) for step in PIPELINE_STEP_ORDER)

    def stop_interaction(self) -> None:
        """Exit active 3D selection/box editing on the viewport without altering effect state."""
        if self._vis_view is not None:
            self._vis_view.stop_vis_sub_roi_interaction()
        if self._section is not None and self.is_available:
            self._section.set_status_text(texts.STATUS_VIS_SUB_ROI_INACTIVE)

    def _connect_signals(self) -> None:
        """
        connect signals from the pipeline model, file controller, viewport,
        and UI section to the appropriate handlers.
        """
        self._pipeline_model.step_status_changed.connect(self._on_step_status_changed)
        self._pipeline_model.step_params_changed.connect(self._on_step_params_changed)
        self._pipeline_model.pipeline_reset.connect(self._on_pipeline_reset)

        self._file_controller.loaded.connect(self._on_file_loaded)
        self._file_controller.closed.connect(self._on_file_closed)

        if self._vis_view is not None:
            self._vis_view.displayed_volume_bounds_updated.connect(self._on_displayed_volume_bounds_updated)
            self._vis_view.vis_sub_roi_selection_started.connect(self._on_viewport_selection_started)
            self._vis_view.vis_sub_roi_bounds_changed.connect(self._on_viewport_bounds_changed)
            self._vis_view.vis_sub_roi_interaction_ended.connect(self._on_viewport_interaction_ended)

        if self._section is not None:
            self._section.enabled_toggled.connect(self._on_enabled_toggled)
            self._section.select_region_clicked.connect(self._on_select_region_clicked)
            self._section.bounds_edited.connect(self._on_bounds_edited)
            self._section.outside_opacity_changed.connect(self._on_outside_opacity_changed)
            self._section.reset_clicked.connect(self._on_reset_clicked)

    def _sync_ui_from_state(self, state: VisSubRoiState) -> None:
        """Push volume bounds and `VisSubRoiState` to the UI section without emitting signals."""
        if self._section is None:
            return
        if self._displayed_volume_bounds is not None:
            self._section.set_volume_bounds(self._displayed_volume_bounds)
        if state.bounds is not None:
            self._section.set_state(state)
        else:
            self._section.set_sub_roi_enabled(state.enabled)
            self._section.set_outside_opacity(state.outside_opacity)

    def _sync_availability(self, *, force_ui_sync: bool = False) -> None:
        """Synchronize UI availability and Sub-ROI effect state with pipeline readiness."""
        available = self.is_available
        was_available = self._last_available
        self._last_available = available

        # if not available, disable effect and lock UI while preserving bounds and opacity
        if not available:
            if self._vis_view is not None:
                self._vis_view.stop_vis_sub_roi_interaction()
                current_state = self._vis_view.vis_sub_roi_state
                if current_state.enabled:
                    self._vis_view.set_vis_sub_roi_enabled(False)
                state_to_show = self._vis_view.vis_sub_roi_state
            else:
                state_to_show = VisSubRoiState(
                    enabled=False,
                    bounds=None,
                    outside_opacity=DEFAULT_OUTSIDE_OPACITY,
                )

            if self._section is not None:
                self._section.set_available(False)
                if force_ui_sync or was_available:
                    self._sync_ui_from_state(state_to_show)
            return

        state_to_show = (
            self._vis_view.vis_sub_roi_state
            if self._vis_view is not None
            else VisSubRoiState(
                enabled=False,
                bounds=None,
                outside_opacity=DEFAULT_OUTSIDE_OPACITY,
            )
        )
        if self._section is not None:
            self._section.set_available(True)
            if force_ui_sync or not was_available:
                self._sync_ui_from_state(state_to_show)

    def _on_step_status_changed(self, _step: PipelineStep, _status: StepStatus) -> None:
        self._sync_availability()

    def _on_step_params_changed(self, _step: PipelineStep) -> None:
        self._sync_availability()

    def _on_pipeline_reset(self) -> None:
        """Disable effect and lock UI on pipeline reset while preserving bounds and opacity."""
        if self._vis_view is not None:
            self._vis_view.stop_vis_sub_roi_interaction()
            self._vis_view.set_vis_sub_roi_enabled(False)
        self._sync_availability(force_ui_sync=True)

    def _on_file_loaded(self, _path: object, _source: FrameSource) -> None:
        """Reset VIS_SUB_ROI completely when a new recording is opened."""
        self._reset_for_new_or_closed_session()

    def _on_file_closed(self) -> None:
        """Reset VIS_SUB_ROI completely when a recording is closed."""
        self._reset_for_new_or_closed_session()

    def _reset_for_new_or_closed_session(self) -> None:
        self._displayed_volume_bounds = None
        default_state = VisSubRoiState(
            enabled=False,
            bounds=None,
            outside_opacity=DEFAULT_OUTSIDE_OPACITY,
        )
        if self._vis_view is not None:
            self._vis_view.reset_vis_sub_roi_state()
        if self._section is not None:
            self._section.set_available(False)
            self._section.set_state(default_state)
            self._section.set_status_text(texts.STATUS_VIS_SUB_ROI_UNAVAILABLE)
        self._last_available = False

    def _on_displayed_volume_bounds_updated(self, bounds: object) -> None:
        if not isinstance(bounds, tuple) or len(bounds) != 6:
            return
        typed_bounds: Bounds6D = (
            float(bounds[0]),
            float(bounds[1]),
            float(bounds[2]),
            float(bounds[3]),
            float(bounds[4]),
            float(bounds[5]),
        )
        if self._displayed_volume_bounds == typed_bounds:
            return

        had_previous_bounds = self._displayed_volume_bounds is not None

        self._displayed_volume_bounds = typed_bounds

        if had_previous_bounds and self._vis_view is not None:
            # if we want to maintain the opacity use clear_vis_sub_roi()
            self._vis_view.reset_vis_sub_roi_state()

        if self._section is not None:
            self._section.set_volume_bounds(typed_bounds)
            if self._vis_view is not None and self._vis_view.vis_sub_roi_state.bounds is not None:
                self._section.set_sub_roi_bounds(self._vis_view.vis_sub_roi_state.bounds)

        self._sync_availability(force_ui_sync=True)

    def _on_select_region_clicked(self) -> None:
        if not self.is_available or self._vis_view is None:
            return
        self.interaction_starting.emit()
        self._vis_view.start_vis_sub_roi_selection()

    def _on_enabled_toggled(self, enabled: bool) -> None:
        if not self.is_available or self._vis_view is None:
            return

        checked = bool(enabled)
        current = self._vis_view.vis_sub_roi_state
        target_bounds = current.bounds
        if checked and target_bounds is None:
            target_bounds = (
                self._section.bounds if self._section is not None else self._displayed_volume_bounds
            )

        updated = VisSubRoiState(
            enabled=checked,
            bounds=target_bounds,
            outside_opacity=current.outside_opacity,
        )
        self._vis_view.set_vis_sub_roi_state(updated)

        if self._section is not None and updated.bounds is not None:
            self._section.set_sub_roi_bounds(updated.bounds)

        if checked and updated.bounds is not None:
            self._vis_view.show_vis_sub_roi_box(updated.bounds)
        elif not checked:
            self._vis_view.stop_vis_sub_roi_interaction()

    def _on_bounds_edited(self, bounds: object) -> None:
        if not self.is_available or self._vis_view is None:
            return
        if not isinstance(bounds, tuple) or len(bounds) != 6:
            return

        typed_bounds: Bounds6D = (
            float(bounds[0]),
            float(bounds[1]),
            float(bounds[2]),
            float(bounds[3]),
            float(bounds[4]),
            float(bounds[5]),
        )
        current = self._vis_view.vis_sub_roi_state
        updated = VisSubRoiState(
            enabled=True,
            bounds=typed_bounds,
            outside_opacity=current.outside_opacity,
        )
        self._vis_view.set_vis_sub_roi_state(updated)

        if self._section is not None:
            self._section.set_sub_roi_enabled(True)
            if self._vis_view.vis_sub_roi_state.bounds is not None:
                self._section.set_sub_roi_bounds(self._vis_view.vis_sub_roi_state.bounds)

        self._vis_view.show_vis_sub_roi_box(self._vis_view.vis_sub_roi_state.bounds)

    def _on_outside_opacity_changed(self, opacity: float) -> None:
        if self._vis_view is None:
            return
        self._vis_view.set_vis_sub_roi_outside_opacity(clamp_outside_opacity(opacity))

    def _on_reset_clicked(self) -> None:
        """Reset Sub-ROI selection and disable effect while preserving outside opacity."""
        if self._vis_view is None:
            return
        preserved_opacity = self._vis_view.vis_sub_roi_state.outside_opacity
        self._vis_view.clear_vis_sub_roi()

        if self._section is not None:
            self._section.set_sub_roi_enabled(False)
            self._section.set_outside_opacity(preserved_opacity)
            if self._displayed_volume_bounds is not None:
                self._section.set_volume_bounds(self._displayed_volume_bounds)
            if self.is_available:
                self._section.set_status_text(texts.STATUS_VIS_SUB_ROI_INACTIVE)

    def _on_viewport_selection_started(self) -> None:
        if self._section is not None and self.is_available:
            self._section.set_sub_roi_enabled(True)

    def _on_viewport_bounds_changed(self, bounds: object) -> None:
        if not isinstance(bounds, tuple) or len(bounds) != 6:
            return
        typed_bounds: Bounds6D = (
            float(bounds[0]),
            float(bounds[1]),
            float(bounds[2]),
            float(bounds[3]),
            float(bounds[4]),
            float(bounds[5]),
        )
        if self._section is not None:
            self._section.set_sub_roi_enabled(True)
            self._section.set_sub_roi_bounds(typed_bounds)

    def _on_viewport_interaction_ended(self) -> None:
        if self._section is not None and self.is_available:
            self._section.set_status_text(texts.STATUS_VIS_SUB_ROI_INACTIVE)
