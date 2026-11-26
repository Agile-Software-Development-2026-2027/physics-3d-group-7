"""Controller synchronizing 3D trajectory rendering with playback frames and layer settings."""

from dataclasses import replace
from typing import Protocol

import pandas as pd
import pyvista as pv
from PySide6.QtCore import QObject

from apkit4d.gui.views.main_window import MainWindow
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


class TrajectoryController(QObject):
    """Coordinates prepared trajectory data, frame slicing, and LeftPanel visual settings."""

    def __init__(
        self,
        window: MainWindow,
        view: TrajectoryView,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._panel = window.left_panel
        self._view = view
        self._prepared: PreparedTrajectories | None = None
        self._current_frame = 0
        self._config = TrajectoryRenderConfig(
            visible=window._show_trajectories_action.isChecked(),
            show_blobs=window._show_blobs_action.isChecked(),
            tail_length=self._panel.appearance_section.trajectory_tail_length,
            color_mode=self._panel.appearance_section.trajectory_color_mode,
            colormap=self._panel.appearance_section.trajectory_colormap,
        )

        self._panel.show_trajectories_toggled.connect(self._on_show_trajectories_toggled)
        self._panel.show_blobs_toggled.connect(self._on_show_blobs_toggled)
        self._panel.appearance_section.trajectory_tail_changed.connect(self._on_tail_length_changed)
        self._panel.appearance_section.trajectory_color_mode_changed.connect(self._on_color_mode_changed)
        self._panel.appearance_section.trajectory_colormap_changed.connect(self._on_colormap_changed)

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

        prepared = PreparedTrajectories.from_dataframe(tracks, dt_s=dt_s)
        self._prepared = prepared if prepared.n_points > 0 else None
        self._render()

    def clear_source(self, *_args: object) -> None:
        """Drop prepared trajectories and clear trajectory actors from the view."""
        self._prepared = None
        self._current_frame = 0
        self._view.clear_trajectories()

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

    def _render(self) -> None:
        if self._prepared is None or not self._config.visible:
            self._view.clear_trajectories()
            return
        poly = build_trajectory_polydata(self._prepared, self._current_frame, self._config)
        self._view.show_trajectories(poly, line_width=self._config.line_width)
