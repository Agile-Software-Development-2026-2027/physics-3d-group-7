from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from apkit4d.gui.controllers.task_runner import wait_for_background_tasks
from apkit4d.gui.controllers.volume_controller import VolumeController
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.preprocessing import PreprocParams
from apkit4d.roi import RegionOfInterest


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
        self.read_calls: list[int] = []

    def read(self, frame: int) -> NDArray:
        self.read_calls.append(frame)
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

    # Wait for frame 0 read and default preprocessing to complete
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)
    assert controller.preproc_params == PreprocParams()
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

    # Apply default PreprocParams to reset preprocessing
    default_params = PreprocParams()
    controller.apply_preproc_params(default_params)
    assert controller.preproc_params == default_params
    qtbot.waitUntil(lambda: len(view.grids) == 3, timeout=5000)


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


def test_volume_controller_preproc_runs_on_roi(qtbot, monkeypatch) -> None:
    """Preprocessing must receive the ROI-cropped volume, not the full frame."""
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    source = FakeSource()
    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    # ROI that crops to half the volume in each spatial dimension (voxel == 1 µm)
    roi = RegionOfInterest(x_min=0.0, x_max=7.0, y_min=0.0, y_max=7.0, z_min=0.0, z_max=3.0)

    captured: list[NDArray] = []

    real_preprocess = __import__("apkit4d.preprocessing", fromlist=["preprocess"]).preprocess

    def capturing_preprocess(vol, params, voxel):
        captured.append(vol)
        return real_preprocess(vol, params, voxel)

    monkeypatch.setattr("apkit4d.gui.controllers.volume_controller.preprocess", capturing_preprocess)

    controller.set_roi(roi)
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    controller.apply_preproc_params(PreprocParams())
    qtbot.waitUntil(lambda: len(view.grids) == 3, timeout=5000)

    assert len(captured) >= 1
    # Every volume passed to preprocess after setting ROI must be the cropped shape, not (8, 16, 16)
    assert all(vol.shape != (8, 16, 16) for vol in captured), "preprocess received the full un-cropped volume"


def test_set_roi_does_not_re_read_disk(qtbot) -> None:
    """Changing the ROI must not trigger another disk read."""
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    source = FakeSource()
    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    reads_after_load = len(source.read_calls)

    roi = RegionOfInterest(x_min=0.0, x_max=7.0, y_min=0.0, y_max=7.0, z_min=0.0, z_max=3.0)
    controller.set_roi(roi)

    # Wait for background preprocessing on the new ROI grid to finish
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)
    # But no extra disk read should have happened
    assert len(source.read_calls) == reads_after_load


def test_set_roi_re_triggers_preprocessing(qtbot, monkeypatch) -> None:
    """When a ROI changes and preprocessing is active, preprocessing reruns on the new crop."""
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    source = FakeSource()
    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    # Enable preprocessing first
    controller.apply_preproc_params(PreprocParams())
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    captured: list[NDArray] = []
    real_preprocess = __import__("apkit4d.preprocessing", fromlist=["preprocess"]).preprocess

    def capturing_preprocess(vol, params, voxel):
        captured.append(vol)
        return real_preprocess(vol, params, voxel)

    monkeypatch.setattr("apkit4d.gui.controllers.volume_controller.preprocess", capturing_preprocess)

    roi = RegionOfInterest(x_min=0.0, x_max=7.0, y_min=0.0, y_max=7.0, z_min=0.0, z_max=3.0)
    controller.set_roi(roi)

    qtbot.waitUntil(lambda: len(captured) == 1, timeout=5000)
    # Preprocessing must have been called with the cropped volume
    assert captured[0].shape != (8, 16, 16)
