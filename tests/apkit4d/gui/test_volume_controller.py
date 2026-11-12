from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from apkit4d.gui.controllers.task_runner import wait_for_background_tasks
from apkit4d.gui.controllers.volume_controller import VolumeController
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.preprocessing import PreprocParams


@dataclass
class FakeInfo:
    voxel: tuple[float, float, float] = (1.0, 1.0, 1.0)
    path: str = "test.czi"
    n_t: int = 5
    n_z: int = 8
    n_y: int = 16
    n_x: int = 16


class FakeSource:
    def __init__(self, data: NDArray | None = None) -> None:
        self.info = FakeInfo()
        self._data = data if data is not None else np.full((8, 16, 16), 100.0, dtype=np.float32)

    def read(self, frame: int) -> NDArray:
        return self._data.copy()


class FakeVolumeView:
    def __init__(self) -> None:
        self.grids: list[tuple[object, bool]] = []

    def show_volume(self, grid: object, reset_camera: bool = True) -> None:
        self.grids.append((grid, reset_camera))


def test_volume_controller_raw_and_preproc(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    source = FakeSource()
    controller.set_source(Path("test.czi"), source)

    # Wait for frame 0 read to complete
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)
    assert controller.preproc_params is None
    assert len(view.grids) == 1
    first_grid, reset_cam = view.grids[0]
    assert reset_cam is True
    assert first_grid.n_points == 8 * 16 * 16

    # Apply preprocessing parameters
    params = PreprocParams(
        lowest_intensity=50.0,
        highest_intensity=150.0,
    )
    controller.apply_preproc_params(params)
    assert controller.preproc_params == params

    # Preprocessing is offloaded to TaskRunner; wait for completion
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)
    second_grid, reset_cam_2 = view.grids[1]
    assert reset_cam_2 is False

    # Apply None to revert to raw volume
    controller.apply_preproc_params(None)
    assert controller.preproc_params is None
    assert len(view.grids) == 3


def test_volume_controller_preproc_failed(qtbot, monkeypatch) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    source = FakeSource()
    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    # Force preprocess to raise error
    def broken_preprocess(*args, **kwargs):
        raise RuntimeError("Filter compute error")

    monkeypatch.setattr("apkit4d.gui.controllers.volume_controller.preprocess", broken_preprocess)

    controller.apply_preproc_params(PreprocParams())
    qtbot.waitUntil(lambda: "Preprocessing failed" in window.statusBar().currentMessage(), timeout=5000)
    wait_for_background_tasks(timeout_s=2.0)
