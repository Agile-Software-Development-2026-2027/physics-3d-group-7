from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from numpy.typing import NDArray

from apkit4d.core.models import PreprocessingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.gui.controllers.task_runner import wait_for_background_tasks
from apkit4d.gui.controllers.volume_controller import PreparedVolume, VolumeController
from apkit4d.gui.models.frame_loading_config import (
    FrameLoadingConfig,
    FrameLoadingMode,
)
from apkit4d.gui.views.main_window import MainWindow


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
        self.grids: list[tuple[object, bool, bool]] = []

    def show_volume(self, grid: object, reset_camera: bool = True, force_update: bool = False) -> None:
        self.grids.append((grid, reset_camera, force_update))


def test_volume_controller_raw_and_preproc(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    source = FakeSource()
    controller.set_source(Path("test.czi"), source)

    # Wait for frame 0 read and default preprocessing to complete
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)
    assert controller.preproc_params == PreprocessingConfig()
    assert len(view.grids) == 1
    first_grid, reset_cam, force_update_1 = view.grids[0]
    assert reset_cam is True
    assert force_update_1 is False
    assert first_grid.n_points == 8 * 16 * 16

    # Apply preprocessing parameters with normalization enabled so reprocessing runs
    params = PreprocessingConfig(
        normalization_enabled=True,
        lowest_intensity=50.0,
        highest_intensity=150.0,
    )
    controller.apply_preproc_params(params)
    assert controller.preproc_params == params

    # Preprocessing is offloaded to TaskRunner; wait for completion
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)
    _, reset_cam_2, force_update_2 = view.grids[1]
    assert reset_cam_2 is False
    assert force_update_2 is True

    # Apply default PreprocParams (normalization_enabled=False) to reset preprocessing
    default_params = PreprocessingConfig()
    controller.apply_preproc_params(default_params)
    assert controller.preproc_params == default_params
    qtbot.waitUntil(lambda: len(view.grids) == 3, timeout=5000)
    _, reset_cam_3, force_update_3 = view.grids[2]
    assert reset_cam_3 is False
    assert force_update_3 is True


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

    controller.apply_preproc_params(PreprocessingConfig(normalization_enabled=True))
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

    real_preprocess = __import__("apkit4d.detection.preprocessing", fromlist=["preprocess"]).preprocess

    def capturing_preprocess(vol, params, voxel):
        captured.append(vol)
        return real_preprocess(vol, params, voxel)

    monkeypatch.setattr("apkit4d.gui.controllers.volume_controller.preprocess", capturing_preprocess)

    controller.set_roi(roi)
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    controller.apply_preproc_params(PreprocessingConfig(normalization_enabled=True))
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
    _, _, force_update = view.grids[1]
    assert force_update is False
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
    controller.apply_preproc_params(PreprocessingConfig(normalization_enabled=True))
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    captured: list[NDArray] = []
    real_preprocess = __import__("apkit4d.detection.preprocessing", fromlist=["preprocess"]).preprocess

    def capturing_preprocess(vol, params, voxel):
        captured.append(vol)
        return real_preprocess(vol, params, voxel)

    monkeypatch.setattr("apkit4d.gui.controllers.volume_controller.preprocess", capturing_preprocess)

    roi = RegionOfInterest(x_min=0.0, x_max=7.0, y_min=0.0, y_max=7.0, z_min=0.0, z_max=3.0)
    controller.set_roi(roi)

    qtbot.waitUntil(lambda: len(captured) == 1, timeout=5000)
    # Preprocessing must have been called with the cropped volume
    assert captured[0].shape != (8, 16, 16)


def test_suggest_intensity_window_does_nothing_without_volume(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    emitted: list[tuple[float, float]] = []
    controller.window_suggested.connect(lambda lo, hi: emitted.append((lo, hi)))

    controller.suggest_intensity_window()
    qtbot.wait(50)
    assert emitted == []


def test_suggest_intensity_window_uses_full_and_roi_volumes(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    controller = VolumeController(window, view)

    data = np.full((8, 16, 16), 10_000.0, dtype=np.float32)
    data[0:4, 0:8, 0:8] = np.linspace(50.0, 200.0, 4 * 8 * 8, dtype=np.float32).reshape(4, 8, 8)

    source = FakeSource(data=data)
    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    # Without ROI, the 99.9th percentile picks up the 10_000 outliers
    with qtbot.waitSignal(controller.window_suggested, timeout=5000) as blocker:
        controller.suggest_intensity_window()
    assert blocker.args[1] == 10_000.0

    # With ROI active, only the cropped [50, 200] region is considered
    roi = RegionOfInterest(x_min=0.0, x_max=7.0, y_min=0.0, y_max=7.0, z_min=0.0, z_max=3.0)
    controller.set_roi(roi)
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    with qtbot.waitSignal(controller.window_suggested, timeout=5000) as roi_blocker:
        controller.suggest_intensity_window()
    lo, hi = roi_blocker.args
    assert 50.0 <= lo < hi <= 200.0

    def open_recording(qtbot, data: NDArray | None = None):
        """A controller with a recording open, its first frame shown and announced."""
        window = MainWindow()
        qtbot.addWidget(window)
        view = FakeVolumeView()
        controller = VolumeController(window, view)
        announced: list[PreparedVolume] = []
        controller.volume_prepared.connect(lambda prepared: announced.append(prepared))
        source = FakeSource(data)
        controller.set_source(Path("test.czi"), source)
        qtbot.waitUntil(lambda: len(announced) == 1, timeout=5000)
        return controller, view, source, announced

    def test_volume_prepared_carries_the_frame_and_the_volumes(qtbot) -> None:
        _, _, source, announced = open_recording(qtbot)

        prepared = announced[0]
        assert prepared.frame == 0
        assert prepared.voxel == source.info.voxel
        assert prepared.offset == (0, 0, 0)  # no ROI: the crop starts at the origin
        assert prepared.roi_volume.shape == (8, 16, 16)
        assert prepared.image.shape == (8, 16, 16)

    def test_volume_prepared_is_emitted_after_the_view_shows_the_volume(qtbot) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        view = FakeVolumeView()
        controller = VolumeController(window, view)
        grids_when_announced: list[int] = []
        controller.volume_prepared.connect(lambda _prepared: grids_when_announced.append(len(view.grids)))

        controller.set_source(Path("test.czi"), FakeSource())
        qtbot.waitUntil(lambda: len(grids_when_announced) == 1, timeout=5000)

        assert grids_when_announced == [1]  # the blobs must not appear before their volume

    def test_volume_prepared_carries_what_preprocessing_returned(qtbot, monkeypatch) -> None:
        produced: list[NDArray] = []

        def fake_preprocess(vol, params, voxel):
            out = np.full(vol.shape, 0.25, dtype=np.float32)
            produced.append(out)
            return out

        monkeypatch.setattr("apkit4d.gui.controllers.volume_controller.preprocess", fake_preprocess)
        data = np.full((8, 16, 16), 100.0, dtype=np.float32)

        _, _, _, announced = open_recording(qtbot, data)

        prepared = announced[0]
        assert prepared.image is produced[0]  # the algorithm looks at the preprocessed volume...
        assert np.array_equal(prepared.roi_volume, data)  # ...and the centroid is weighted by the raw one

    def test_a_new_frame_is_announced_with_its_own_volume(qtbot) -> None:
        controller, _, _, announced = open_recording(qtbot)

        controller.show_frame(1)
        qtbot.waitUntil(lambda: len(announced) == 2, timeout=5000)

        assert announced[1].frame == 1
        assert announced[1] is not announced[0]

    def test_set_roi_announces_the_cropped_volume(qtbot) -> None:
        controller, _, source, announced = open_recording(qtbot)

        controller.set_roi(RegionOfInterest(x_min=0.0, x_max=7.0, y_min=0.0, y_max=7.0, z_min=0.0, z_max=3.0))
        qtbot.waitUntil(lambda: len(announced) == 2, timeout=5000)

        prepared = announced[1]
        assert prepared.frame == 0
        assert prepared.roi_volume.shape != (8, 16, 16)
        assert (
            prepared.image.shape == prepared.roi_volume.shape
        )  # preprocessed on the crop, not on the full frame
        assert len(source.read_calls) == 1  # the crop was cut from the volume in memory

    def test_prepared_offset_locates_the_crop_inside_the_full_volume(qtbot) -> None:
        # every voxel has a different value, so a crop can only match at its real position
        data = np.arange(8 * 16 * 16, dtype=np.float32).reshape(8, 16, 16)
        controller, _, _, announced = open_recording(qtbot, data)

        controller.set_roi(
            RegionOfInterest(x_min=4.0, x_max=11.0, y_min=2.0, y_max=9.0, z_min=1.0, z_max=4.0)
        )
        qtbot.waitUntil(lambda: len(announced) == 2, timeout=5000)

        prepared = announced[1]
        z, y, x = prepared.offset  # voxels, (z, y, x)
        dz, dy, dx = prepared.roi_volume.shape
        assert prepared.offset != (0, 0, 0)
        assert np.array_equal(data[z : z + dz, y : y + dy, x : x + dx], prepared.roi_volume)

    def test_apply_preproc_params_announces_a_new_image_on_the_same_crop(qtbot) -> None:
        controller, _, source, announced = open_recording(qtbot)

        controller.apply_preproc_params(PreprocessingConfig(lowest_intensity=50.0, highest_intensity=150.0))
        qtbot.waitUntil(lambda: len(announced) == 2, timeout=5000)

        assert announced[1].frame == announced[0].frame
        assert announced[1].image is not announced[0].image
        assert announced[1].roi_volume is announced[0].roi_volume  # nothing was read or cropped again
        assert len(source.read_calls) == 1

    def test_opening_another_recording_announces_its_first_frame(qtbot) -> None:
        controller, _, _, announced = open_recording(qtbot)

        controller.set_source(Path("other.czi"), FakeSource())
        qtbot.waitUntil(lambda: len(announced) == 2, timeout=5000)

        assert announced[1].frame == 0
        assert announced[1] is not announced[0]

    def test_a_volume_that_cannot_be_shown_is_not_announced(qtbot, monkeypatch) -> None:
        window = MainWindow()
        qtbot.addWidget(window)
        view = FakeVolumeView()
        controller = VolumeController(window, view)
        announced: list[PreparedVolume] = []
        controller.volume_prepared.connect(lambda prepared: announced.append(prepared))
        # a 2D result: the view refuses it ("not 3D") and the controller reports the failure
        monkeypatch.setattr(
            "apkit4d.gui.controllers.volume_controller.preprocess",
            lambda vol, params, voxel: np.zeros((4, 4), dtype=np.float32),
        )

        with qtbot.waitSignal(controller.failed, timeout=5000):
            controller.set_source(Path("test.czi"), FakeSource())
        qtbot.wait(100)

        assert view.grids == []
        assert announced == []


@pytest.fixture
def cache_controller(qtbot, monkeypatch):
    memory = SimpleNamespace(
        total=100_000_000_000,
        available=60_000_000_000,
    )
    monkeypatch.setattr("psutil.virtual_memory", lambda: memory)

    window = MainWindow()
    qtbot.addWidget(window)

    view = FakeVolumeView()
    controller = VolumeController(window, view, parent=window)
    controller.set_frame_loading_config(FrameLoadingConfig(mode=FrameLoadingMode.AUTOMATIC))

    yield controller, view, memory

    controller.clear_source()


def test_cached_frame_is_not_read_again(qtbot, cache_controller) -> None:
    controller, view, _ = cache_controller
    source = FakeSource()

    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    controller.show_frame(1)
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    controller.show_frame(0)
    qtbot.waitUntil(lambda: len(view.grids) == 3, timeout=5000)

    assert source.read_calls == [0, 1]


def test_lazy_loading_clears_cache(qtbot, cache_controller) -> None:
    controller, view, _ = cache_controller
    source = FakeSource()

    controller.set_source(Path("test.czi"), source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    assert len(controller._frame_cache) == 1

    controller.set_frame_loading_config(FrameLoadingConfig(mode=FrameLoadingMode.LAZY))

    assert len(controller._frame_cache) == 0
    assert controller._frame_cache.size_bytes == 0
    assert not controller._memory_timer.isActive()

    controller.show_frame(0)
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    assert source.read_calls == [0, 0]
    assert len(controller._frame_cache) == 0


def test_cache_is_cleared_when_source_changes(qtbot, cache_controller) -> None:
    controller, view, _ = cache_controller

    first_source = FakeSource()
    second_source = FakeSource()

    controller.set_source(Path("first.czi"), first_source)
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    controller.show_frame(1)
    qtbot.waitUntil(lambda: len(view.grids) == 2, timeout=5000)

    assert len(controller._frame_cache) == 2

    controller.set_source(Path("second.czi"), second_source)
    qtbot.waitUntil(lambda: len(view.grids) == 3, timeout=5000)

    assert second_source.read_calls == [0]
    assert len(controller._frame_cache) == 1
    assert controller._frame_cache.get(1) is None


def test_memory_timer_reduces_cache(qtbot, cache_controller) -> None:
    controller, view, memory = cache_controller

    controller.set_source(Path("test.czi"), FakeSource())
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    assert controller._memory_timer.isActive()
    assert controller._frame_cache.size_bytes > 0

    memory.available = 0

    qtbot.waitUntil(
        lambda: controller._frame_cache.size_bytes == 0,
        timeout=3000,
    )

    assert controller._frame_cache.max_bytes == 0

    memory.available = 60_000_000_000

    qtbot.waitUntil(
        lambda: controller._frame_cache.max_bytes > 0,
        timeout=3000,
    )


def test_closing_source_releases_cache(qtbot, cache_controller) -> None:
    controller, view, _ = cache_controller

    controller.set_source(Path("test.czi"), FakeSource())
    qtbot.waitUntil(lambda: len(view.grids) == 1, timeout=5000)

    controller.clear_source()

    assert len(controller._frame_cache) == 0
    assert controller._frame_cache.size_bytes == 0
    assert not controller._memory_timer.isActive()
