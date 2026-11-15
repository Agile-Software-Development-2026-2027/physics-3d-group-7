"""Unit tests for TrajectoryController and its LeftPanel/TrajectoryView integration."""

import pandas as pd
import pytest
import pyvista as pv
from PySide6.QtWidgets import QCheckBox, QComboBox, QSpinBox

from apkit4d.gui.constants import names
from apkit4d.gui.controllers.trajectory_controller import TrajectoryController
from apkit4d.gui.views.panels.left_panel import LeftPanel
from apkit4d.visualization.data_mapper import TrajectoryColorMode


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
    panel = LeftPanel()
    qtbot.addWidget(panel)
    view = _FakeTrajectoryView()
    controller = TrajectoryController(panel, view)
    return panel, view, controller


def test_trajectory_controller_renders_and_updates_on_frame_and_panel_changes(setup) -> None:
    panel, view, controller = setup
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
    traj_cb = panel.findChild(QCheckBox, names.SHOW_TRAJECTORIES_CHECKBOX)
    blobs_cb = panel.findChild(QCheckBox, names.SHOW_BLOBS_CHECKBOX)

    cleared_before = view.cleared_count
    traj_cb.setChecked(False)
    assert view.cleared_count == cleared_before + 1

    # Advancing frame while hidden stays cleared
    controller.on_set_frame(2)
    assert view.cleared_count == cleared_before + 2

    traj_cb.setChecked(True)
    assert view.trajectories[-1][0].n_points == 2

    blobs_cb.setChecked(False)
    assert view.blobs_visible[-1] is False

    controller.clear_source()
    assert controller.current_frame == 0
    assert view.cleared_count == cleared_before + 3
