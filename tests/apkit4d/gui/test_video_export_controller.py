from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QPushButton, QSpinBox

from apkit4d.gui.constants import names
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.video_export_controller import VideoExportController
from apkit4d.gui.views.playback.playback_bar import PlaybackBar
from apkit4d.gui.views.widgets.dialogs.video_export_dialog import VideoExportDialog
from apkit4d.io.czi import CziInfo, CziSource


class MockView:
    def __init__(self, shape: tuple[int, int, int] = (64, 64, 3)) -> None:
        self.shape = shape
        self.screenshot_call_count = 0
        self.screenshot_window_sizes: list[tuple[int, int] | None] = []

    def screenshot(self, window_size: tuple[int, int] | None = None) -> np.ndarray:
        self.screenshot_call_count += 1
        self.screenshot_window_sizes.append(window_size)
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
        controller = VideoExportController(playback_controller=mock_playback)
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
        controller = VideoExportController(playback_controller=mock_playback)

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
            controller.set_resolution(1280, 720)
        assert controller.resolution == (1280, 720)

        with qtbot.waitSignal(controller.config_changed):
            controller.set_preset("fast")
        assert controller.preset == "fast"

        out_path = tmp_path / "output.mp4"
        with qtbot.waitSignal(controller.config_changed):
            controller.set_output_path(out_path)
        assert controller.output_path == out_path

    def test_set_frame_range(self, mock_playback, qtbot) -> None:
        controller = VideoExportController(playback_controller=mock_playback)
        with qtbot.waitSignal(controller.config_changed):
            controller.set_frame_range(1, 5)
        assert controller.first_frame == 1
        assert controller.last_frame == 5
        assert controller.export_frame_count == 5

    def test_set_and_clear_source(self, mock_playback, mock_source, tmp_path: Path) -> None:
        controller = VideoExportController(playback_controller=mock_playback)
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
    def test_dialog_opens_output_folder_after_success(
        self, mock_playback, qtbot, tmp_path: Path, monkeypatch
    ) -> None:
        controller = VideoExportController(playback_controller=mock_playback, view=MockView())
        dialog = VideoExportDialog(controller)
        qtbot.addWidget(dialog)
        button = dialog.findChild(QPushButton, names.VIDEO_EXPORT_OPEN_FOLDER_BUTTON)
        assert button is not None
        assert button.isHidden()

        output_path = tmp_path / "export.mp4"
        opened_urls = []
        monkeypatch.setattr(
            "apkit4d.gui.views.widgets.dialogs.video_export_dialog.QDesktopServices.openUrl",
            lambda url: opened_urls.append(url) or True,
        )
        controller.export_succeeded.emit(output_path)

        assert not button.isHidden()
        button.click()
        assert len(opened_urls) == 1
        assert Path(opened_urls[0].toLocalFile()) == tmp_path

    def test_dialog_uses_one_based_frame_numbers(self, mock_playback, qtbot) -> None:
        controller = VideoExportController(
            playback_controller=mock_playback,
            view=MockView(),
        )
        controller.set_frame_range(2, 7)
        dialog = VideoExportDialog(controller)
        qtbot.addWidget(dialog)

        first_frame = dialog.findChild(QSpinBox, names.VIDEO_EXPORT_FIRST_FRAME)
        last_frame = dialog.findChild(QSpinBox, names.VIDEO_EXPORT_LAST_FRAME)
        assert first_frame is not None
        assert last_frame is not None
        assert (first_frame.value(), last_frame.value()) == (3, 8)

        first_frame.setValue(4)
        last_frame.setValue(9)

        assert (controller.first_frame, controller.last_frame) == (3, 8)
        assert mock_playback.frame == 3

    def test_dialog_resolution_controls_update_export_settings(self, mock_playback, qtbot) -> None:
        view = MockView()
        controller = VideoExportController(playback_controller=mock_playback, view=view)
        dialog = VideoExportDialog(controller)
        qtbot.addWidget(dialog)

        width = dialog.findChild(QSpinBox, names.VIDEO_EXPORT_WIDTH)
        height = dialog.findChild(QSpinBox, names.VIDEO_EXPORT_HEIGHT)
        assert width is not None
        assert height is not None
        assert (width.value(), height.value()) == (1920, 1080)

        width.setValue(1280)
        height.setValue(720)

        assert controller.resolution == (1280, 720)
        assert view.screenshot_window_sizes[-1] == (1280, 720)

    def test_dialog_exit_restores_playback_frame(self, mock_playback, qtbot) -> None:
        mock_playback.go_to_frame(6)
        controller = VideoExportController(
            playback_controller=mock_playback,
            view=MockView(),
        )
        dialog = VideoExportDialog(controller)
        qtbot.addWidget(dialog)

        assert mock_playback.frame != 6

        dialog.reject()

        assert mock_playback.frame == 6

    def test_live_viewport_export_stepping(self, mock_playback, qtbot, tmp_path: Path) -> None:
        view = MockView(shape=(32, 32, 3))
        volume = MockVolumeController()
        controller = VideoExportController(
            playback_controller=mock_playback,
            view=view,
            volume_controller=volume,  # type: ignore
        )
        out = tmp_path / "live_export.mp4"
        controller.set_frame_range(0, 2)
        controller.set_resolution(1280, 720)
        controller.set_output_path(out)
        previewed_frames: list[int] = []
        controller.preview_ready.connect(lambda frame, _: previewed_frames.append(frame))

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
            playback_controller=mock_playback,
            view=view,
            volume_controller=volume,  # type: ignore
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
            playback_controller=mock_playback,
            view=view,
            volume_controller=volume,  # type: ignore
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
