"""Unit tests for TrajectoryController and its LeftPanel/TrajectoryView integration."""

import numpy as np
import pandas as pd
import pytest
import pyvista as pv
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QComboBox, QSpinBox

from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.trajectory_controller import TrajectoryController
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.visualization.data_mapper import PreparedTrajectories, TrajectoryColorMode
from apkit4d.visualization.viewport import ScalarBarMode, Viewport


class _FakeTrajectoryView:
    def __init__(self) -> None:
        self.trajectories: list[tuple[pv.PolyData | None, float]] = []
        self.cleared_count = 0
        self.blobs_visible: list[bool] = []

    def show_trajectories(
        self,
        highlighted: pv.PolyData | None,
        *,
        line_width: float = 2.5,
    ) -> None:
        self.trajectories.append((highlighted, line_width))

    def clear_trajectories(self) -> None:
        self.cleared_count += 1

    def set_blobs_visible(self, visible: bool) -> None:
        self.blobs_visible.append(visible)


def _sample_tracks() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "track_id": [1, 1, 1, 1],
            "frame": [0, 1, 2, 3],
            "x_um": [0.0, 2.0, 6.0, 12.0],
            "y_um": [0.0, 0.0, 0.0, 0.0],
            "z_um": [0.0, 0.0, 0.0, 0.0],
            "t_s": [0.0, 0.1, 0.2, 0.3],
        }
    )


@pytest.fixture
def setup(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    view = _FakeTrajectoryView()
    controller = TrajectoryController(window, view)
    return window, view, controller


def test_trajectory_controller_renders_and_updates_on_frame_and_panel_changes(setup) -> None:
    window, view, controller = setup
    panel = window.left_panel
    assert view.blobs_visible == [True]

    controller.set_trajectories(_sample_tracks(), dt_s=0.1, current_frame=0)
    assert view.trajectories[-1][0].n_points == 0

    controller.on_set_frame(3)
    assert view.trajectories[-1][0].n_points == 4

    # Adjusting tail length shrinks rendered points live
    tail_spin = panel.findChild(QSpinBox, names.TRAJECTORY_TAIL_SPINBOX)
    tail_spin.setValue(1)
    assert view.trajectories[-1][0].n_points == 2

    # Switching color mode and colormap triggers re-render
    mode_combo = panel.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO)
    mode_combo.setCurrentIndex(1)
    assert controller.config.color_mode == TrajectoryColorMode.TRACK_ID
    speed_colors = view.trajectories[-2][0].point_data["rgb"]
    tid_colors = view.trajectories[-1][0].point_data["rgb"]
    assert not (speed_colors == tid_colors).all()

    mode_combo.setCurrentIndex(0)
    cmap_combo = panel.findChild(QComboBox, names.TRAJECTORY_COLORMAP_COMBO)
    cmap_combo.setCurrentIndex(1)
    assert controller.config.colormap == cmap_combo.currentText()

    # Toggling trajectory visibility clears/restores trajectories; toggling blobs updates view
    traj_cb = window.findChild(QAction, names.SHOW_TRAJECTORIES_ACTION)
    blobs_cb = window.findChild(QAction, names.SHOW_BLOBS_ACTION)

    cleared_before = view.cleared_count
    assert traj_cb is not None
    traj_cb.setChecked(False)
    assert view.cleared_count == cleared_before + 1

    # Advancing frame while hidden stays cleared
    controller.on_set_frame(2)
    assert view.cleared_count == cleared_before + 2

    traj_cb.setChecked(True)
    assert view.trajectories[-1][0].n_points == 2

    assert blobs_cb is not None
    blobs_cb.setChecked(False)
    assert view.blobs_visible[-1] is False

    controller.clear_source()
    assert controller.current_frame == 0
    assert view.cleared_count == cleared_before + 3


class _FakeScalarBarTrajectoryView(_FakeTrajectoryView):
    def __init__(self) -> None:
        super().__init__()
        self.velocity_bar_calls: list[tuple[float, float, str, bool, str]] = []
        self.restore_calls: int = 0

    def show_velocity_scalar_bar(
        self,
        vmin: float,
        vmax: float,
        colormap: str,
        *,
        visible: bool = True,
        title: str = "",
    ) -> None:
        self.velocity_bar_calls.append((vmin, vmax, colormap, visible, title))

    def restore_volume_scalar_bar(self) -> None:
        self.restore_calls += 1


def test_velocity_scalar_bar_switches_on_tracking_and_follows_panel_and_reset(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window.left_panel
    view = _FakeScalarBarTrajectoryView()
    controller = TrajectoryController(window, view)

    tracks = _sample_tracks()
    expected_vmax = PreparedTrajectories.from_dataframe(tracks, dt_s=0.1).speed_vmax

    controller.set_trajectories(tracks, dt_s=0.1, current_frame=0)
    assert view.restore_calls == 0
    assert view.velocity_bar_calls[-1] == (
        0.0,
        expected_vmax,
        controller.config.colormap,
        True,
        texts.SCALAR_BAR_VELOCITY,
    )

    # Frame change does not restore volume bar
    controller.on_set_frame(0)
    assert view.restore_calls == 0

    # Switching to TRACK_ID hides velocity bar without restoring volume bar
    mode_combo = panel.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO)
    assert mode_combo is not None
    mode_combo.setCurrentIndex(1)
    assert view.velocity_bar_calls[-1][3] is False
    assert view.restore_calls == 0

    # Switching back to SPEED shows velocity bar again; changing colormap updates it
    mode_combo.setCurrentIndex(0)
    assert view.velocity_bar_calls[-1][3] is True
    cmap_combo = panel.findChild(QComboBox, names.TRAJECTORY_COLORMAP_COMBO)
    assert cmap_combo is not None
    cmap_combo.setCurrentIndex(1)
    assert view.velocity_bar_calls[-1][2] == cmap_combo.currentText()

    # Hiding trajectories hides velocity bar instead of restoring "values"
    panel.show_trajectories_toggled.emit(False)
    assert view.velocity_bar_calls[-1][3] is False
    assert view.restore_calls == 0

    panel.show_trajectories_toggled.emit(True)
    assert view.velocity_bar_calls[-1][3] is True

    # Reset / file change restores volume bar
    controller.clear_source()
    assert view.restore_calls == 1


def test_velocity_scalar_bar_switches_even_when_tracking_produces_zero_tracks(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = _FakeScalarBarTrajectoryView()
    controller = TrajectoryController(window, view)

    controller.set_trajectories(pd.DataFrame(), dt_s=0.1, current_frame=0)

    assert view.restore_calls == 0
    assert view.velocity_bar_calls[-1] == (
        0.0,
        1.0,
        controller.config.colormap,
        True,
        texts.SCALAR_BAR_VELOCITY,
    )


def test_trajectory_controller_switches_scalar_bar_on_real_viewport(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    panel = window.left_panel
    vp = Viewport()
    qtbot.addWidget(vp)

    try:
        grid = pv.ImageData(dimensions=(5, 5, 5))
        grid.point_data["values"] = np.linspace(0.0, 50.0, grid.n_points, dtype=np.float32)
        vp.show_volume(grid, reset_camera=False)
        assert "values" in vp.plotter.scalar_bars

        controller = TrajectoryController(window, vp)
        controller.set_trajectories(_sample_tracks(), dt_s=0.1, current_frame=3)

        assert vp.scalar_bar_mode == ScalarBarMode.VELOCITY
        assert "values" not in vp.plotter.scalar_bars
        assert texts.SCALAR_BAR_VELOCITY in vp.plotter.scalar_bars
        assert vp.plotter.scalar_bars[texts.SCALAR_BAR_VELOCITY].GetVisibility() == 1

        mode_combo = panel.findChild(QComboBox, names.TRAJECTORY_COLOR_MODE_COMBO)
        assert mode_combo is not None
        mode_combo.setCurrentIndex(1)
        assert vp.plotter.scalar_bars[texts.SCALAR_BAR_VELOCITY].GetVisibility() == 0
        assert "values" not in vp.plotter.scalar_bars

        controller.clear_source()
        assert vp.scalar_bar_mode == ScalarBarMode.VOLUME
        assert texts.SCALAR_BAR_VELOCITY not in vp.plotter.scalar_bars
        assert "values" in vp.plotter.scalar_bars
    finally:
        vp.plotter.close()
