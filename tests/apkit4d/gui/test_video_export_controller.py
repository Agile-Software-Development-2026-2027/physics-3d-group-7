"""Tests for VideoExportController."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal

from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.video_export_controller import VideoExportController
from apkit4d.gui.views.widgets.playback_bar import PlaybackBar
from apkit4d.io.czi import CziInfo, CziSource


class MockView:
    def __init__(self, shape: tuple[int, int, int] = (64, 64, 3)) -> None:
        self.shape = shape
        self.screenshot_call_count = 0

    def screenshot(self) -> np.ndarray:
        self.screenshot_call_count += 1
        return np.full(self.shape, fill_value=self.screenshot_call_count * 10, dtype=np.uint8)


class MockPreparedVolume:
    def __init__(self, frame: int) -> None:
        self.frame = frame


class MockVolumeController(QObject):
    volume_prepared = Signal(object)
    failed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._busy = False
        self._current_frame = 0


@pytest.fixture
def mock_playback(qtbot):
    bar = PlaybackBar()
    qtbot.addWidget(bar)
    controller = PlaybackController(bar)
    controller.set_frame_count(10)
    return controller


@pytest.fixture
def mock_source(tmp_path: Path):
    source = MagicMock(spec=CziSource)
    source.info = CziInfo(
        path=str(tmp_path / "test.czi"),
        n_t=8,
        n_z=10,
        n_y=20,
        n_x=20,
        n_c=1,
        dtype="uint16",
        px_size_x=1.0,
        px_size_y=1.0,
        px_size_z=1.0,
        dt_s=0.5,
        dt_source="test",
    )
    return source


class TestVideoExportControllerConfig:
    def test_initialization_defaults(self, mock_playback) -> None:
        controller = VideoExportController(playback=mock_playback)
        assert controller.total_frames == 10
        assert controller.first_frame == 0
        assert controller.last_frame == 9
        assert controller.crf == 23
        assert controller.fps == int(mock_playback.speed)
        assert controller.preset == "medium"
        assert controller.output_path is None
        assert not controller.is_exporting
        assert controller.is_available

    def test_set_properties_and_emits_config_changed(self, mock_playback, qtbot, tmp_path: Path) -> None:
        controller = VideoExportController(playback=mock_playback)

        with qtbot.waitSignal(controller.config_changed):
            controller.set_first_frame(2)
        assert controller.first_frame == 2

        with qtbot.waitSignal(controller.config_changed):
            controller.set_last_frame(7)
        assert controller.last_frame == 7

        with qtbot.waitSignal(controller.config_changed):
            controller.set_crf(28)
        assert controller.crf == 28

        # CRF clamping
        controller.set_crf(999)
        assert controller.crf == 51
        controller.set_crf(-10)
        assert controller.crf == 0

        with qtbot.waitSignal(controller.config_changed):
            controller.set_fps(30)
        assert controller.fps == 30

        with qtbot.waitSignal(controller.config_changed):
            controller.set_preset("fast")
        assert controller.preset == "fast"

        out_path = tmp_path / "output.mp4"
        with qtbot.waitSignal(controller.config_changed):
            controller.set_output_path(out_path)
        assert controller.output_path == out_path

    def test_set_frame_range(self, mock_playback, qtbot) -> None:
        controller = VideoExportController(playback=mock_playback)
        with qtbot.waitSignal(controller.config_changed):
            controller.set_frame_range(1, 5)
        assert controller.first_frame == 1
        assert controller.last_frame == 5
        assert controller.export_frame_count == 5

    def test_set_and_clear_source(self, mock_playback, mock_source, tmp_path: Path) -> None:
        controller = VideoExportController(playback=mock_playback)
        czi_path = tmp_path / "sample.czi"

        controller.set_source(czi_path, mock_source)
        assert controller.total_frames == 8
        assert controller.first_frame == 0
        assert controller.last_frame == 7
        assert controller.output_path == tmp_path / "sample_export.mp4"
        assert controller.is_available

        controller.clear_source()
        assert controller.total_frames == 0
        assert controller.first_frame == 0
        assert controller.last_frame == 0
        assert controller.output_path is None
        assert not controller.is_available


class TestVideoExportExecution:
    def test_live_viewport_export_stepping(self, mock_playback, qtbot, tmp_path: Path) -> None:
        view = MockView(shape=(32, 32, 3))
        volume = MockVolumeController()
        controller = VideoExportController(
            playback=mock_playback,
            view=view,
            volume=volume,  # type: ignore
        )
        out = tmp_path / "live_export.mp4"
        controller.set_frame_range(0, 2)
        controller.set_output_path(out)

        with qtbot.waitSignal(controller.export_started):
            controller.start_export()

        # Step 0: Frame 0 is captured
        # Step 1: Playback requested frame 1 -> simulate volume_prepared for frame 1
        qtbot.waitUntil(lambda: mock_playback.frame == 1, timeout=2000)
        volume.volume_prepared.emit(MockPreparedVolume(frame=1))

        # Step 2: Playback requested frame 2 -> simulate volume_prepared for frame 2
        qtbot.waitUntil(lambda: mock_playback.frame == 2, timeout=2000)
        with qtbot.waitSignal(controller.export_succeeded, timeout=3000):
            volume.volume_prepared.emit(MockPreparedVolume(frame=2))

        assert out.exists()
        assert out.stat().st_size > 0
        assert view.screenshot_call_count == 3

    def test_cancel_export(self, mock_playback, qtbot, tmp_path: Path) -> None:
        view = MockView(shape=(32, 32, 3))
        volume = MockVolumeController()
        controller = VideoExportController(
            playback=mock_playback,
            view=view,
            volume=volume,  # type: ignore
        )
        out = tmp_path / "cancel_live.mp4"
        controller.set_frame_range(0, 5)
        controller.set_output_path(out)

        controller.start_export()
        assert controller.is_exporting

        with qtbot.waitSignal(controller.export_cancelled):
            controller.cancel_export()

        assert not controller.is_exporting
        assert not out.exists()

    def test_volume_failure_cancels_export(self, mock_playback, qtbot, tmp_path: Path) -> None:
        view = MockView(shape=(32, 32, 3))
        volume = MockVolumeController()
        controller = VideoExportController(
            playback=mock_playback,
            view=view,
            volume=volume,  # type: ignore
        )
        out = tmp_path / "fail_live.mp4"
        controller.set_frame_range(0, 2)
        controller.set_output_path(out)

        controller.start_export()
        # Simulate volume load failure
        with qtbot.waitSignal(controller.export_failed):
            volume.failed.emit()

        assert not controller.is_exporting
        assert not out.exists()
