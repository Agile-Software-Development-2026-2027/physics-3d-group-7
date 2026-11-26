"""Controller synchronizing 3D trajectory rendering with playback frames and layer settings."""

from dataclasses import replace
from typing import Protocol, runtime_checkable

import pandas as pd
import pyvista as pv
from PySide6.QtCore import QObject

from apkit4d.gui.constants import texts
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.visualization.data_mapper import (
    PreparedTrajectories,
    TrajectoryColorMode,
    TrajectoryRenderConfig,
    build_trajectory_polydata,
)


class TrajectoryView(Protocol):
    """What `TrajectoryController` needs from the 3D view. `Viewport` provides it."""

    def show_trajectories(
        self,
        highlighted: pv.PolyData | None,
        *,
        line_width: float = 2.5,
    ) -> None: ...

    def clear_trajectories(self) -> None: ...

    def set_blobs_visible(self, visible: bool) -> None: ...


@runtime_checkable
class VelocityScalarBarView(Protocol):
    """Optional scalar bar switching contract provided by `Viewport`."""

    def show_velocity_scalar_bar(
        self,
        vmin: float,
        vmax: float,
        colormap: str,
        *,
        visible: bool = True,
        title: str = ...,
    ) -> None: ...

    def restore_volume_scalar_bar(self) -> None: ...


class TrajectoryController(QObject):
    """Coordinates prepared trajectory data, frame slicing, and LeftPanel visual settings."""

    def __init__(
        self,
        panel: LeftPanel,
        view: TrajectoryView,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._panel = panel
        self._view = view
        self._scalar_bar_view: VelocityScalarBarView | None = (
            view if isinstance(view, VelocityScalarBarView) else None
        )
        self._prepared: PreparedTrajectories | None = None
        self._has_tracking_result: bool = False
        self._velocity_vmax: float = 1.0
        self._current_frame = 0
        self._config = TrajectoryRenderConfig(
            # TODO: layers
            # visible=panel.layers_section.show_trajectories,
            # show_blobs=panel.layers_section.show_blobs,
            visible=True,
            show_blobs=True,
            tail_length=panel.appearance_section.trajectory_tail_length,
            color_mode=panel.appearance_section.trajectory_color_mode,
            colormap=panel.appearance_section.trajectory_colormap,
        )

        panel.show_trajectories_toggled.connect(self._on_show_trajectories_toggled)
        panel.show_blobs_toggled.connect(self._on_show_blobs_toggled)
        panel.appearance_section.trajectory_tail_changed.connect(self._on_tail_length_changed)
        panel.appearance_section.trajectory_color_mode_changed.connect(self._on_color_mode_changed)
        panel.appearance_section.trajectory_colormap_changed.connect(self._on_colormap_changed)

        view.set_blobs_visible(self._config.show_blobs)

    @property
    def config(self) -> TrajectoryRenderConfig:
        """Current trajectory visual configuration."""
        return self._config

    @property
    def current_frame(self) -> int:
        """Last playback frame index rendered for trajectories."""
        return self._current_frame

    def set_trajectories(
        self,
        tracks: pd.DataFrame | None,
        *,
        dt_s: float | None = None,
        current_frame: int | None = None,
    ) -> None:
        """Prepare `tracks` once and immediately render trajectories up to the active frame."""
        if current_frame is not None:
            self._current_frame = int(current_frame)

        # switched to an if to handle the tracks are none so the velocity scalar bar
        # is set to default values, NOT back to volume scalar bar
        if tracks is None:
            self._prepared = None
            self._has_tracking_result = False
            self._velocity_vmax = 1.0
        else:
            prepared = PreparedTrajectories.from_dataframe(tracks, dt_s=dt_s)
            self._prepared = prepared if prepared.n_points > 0 else None
            self._has_tracking_result = True
            self._velocity_vmax = prepared.speed_vmax

        self._render()
        self._sync_velocity_scalar_bar()

    def clear_source(self, *_args: object) -> None:
        """Drop prepared trajectories and clear trajectory actors from the view."""
        self._prepared = None
        self._has_tracking_result = False
        self._velocity_vmax = 1.0
        self._current_frame = 0
        self._view.clear_trajectories()
        self._sync_velocity_scalar_bar()

    def on_set_frame(self, frame: int) -> None:
        """Re-slice and update visible trajectory segments for `frame`."""
        self._current_frame = int(frame)
        self._render()

    def _on_show_trajectories_toggled(self, visible: bool) -> None:
        self._update_config(visible=visible)

    def _on_show_blobs_toggled(self, visible: bool) -> None:
        self._config = replace(self._config, show_blobs=visible)
        self._view.set_blobs_visible(visible)

    def _on_tail_length_changed(self, tail_length: int) -> None:
        self._update_config(tail_length=int(tail_length))

    def _on_color_mode_changed(self, color_mode: TrajectoryColorMode) -> None:
        self._update_config(color_mode=color_mode)

    def _on_colormap_changed(self, colormap: str) -> None:
        self._update_config(colormap=colormap)

    def _update_config(self, **changes: object) -> None:
        self._config = replace(self._config, **changes)  # type: ignore[arg-type]
        self._render()
        self._sync_velocity_scalar_bar()

    def _sync_velocity_scalar_bar(self) -> None:
        if self._scalar_bar_view is None:
            return
        if not self._has_tracking_result:
            self._scalar_bar_view.restore_volume_scalar_bar()
            return
        visible = self._config.visible and self._config.color_mode == TrajectoryColorMode.SPEED
        self._scalar_bar_view.show_velocity_scalar_bar(
            0.0,
            self._velocity_vmax,
            self._config.colormap,
            visible=visible,
            title=texts.SCALAR_BAR_VELOCITY,
        )

    def _render(self) -> None:
        if self._prepared is None or not self._config.visible:
            self._view.clear_trajectories()
            return
        poly = build_trajectory_polydata(self._prepared, self._current_frame, self._config)
        self._view.show_trajectories(poly, line_width=self._config.line_width)
