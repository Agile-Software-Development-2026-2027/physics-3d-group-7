"""
Controller for exporting viewport frames to a video with configurable compression.

We extract frames from the 3D viewport by updating the playback position, then
we encode the frames into a video, while emitting progress signals for the UI.
"""

from contextlib import suppress
from pathlib import Path
from typing import Protocol

import imageio
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QTimer, Signal

from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.volume_controller import VolumeController


class VideoExportView(Protocol):
    """What the video export controller needs from the 3D view."""

    def screenshot(self, window_size: tuple[int, int] | None = None) -> NDArray: ...


class VideoExportController(QObject):
    """
    Coordinates exporting viewport frames to a compressed video file.

    The export steps through the underlying playback. That is because we need to
    physically take a screenshot of all the frames in the playback.

    Args:
        playback: PlaybackController for timeline and frame navigation.
        view: 3D view from which we capture the screenshots.
        volume: Optional VolumeController to synchronize when frames finish rendering.
        files: Optional FileController to automatically track open recordings.
        parent: Qt parent QObject.

    Signals:
        export_started: Emitted when export begins.
        progress_changed: Emitted with (current_done, total_frames) as export advances.
        export_succeeded: Emitted with the resolved Path when export finishes successfully.
        export_failed: Emitted with an error message string when export encounters an error.
        export_cancelled: Emitted when export is aborted by the user.
        preview_ready: Emitted with (frame_index, frame_data) when a preview frame is available.
        config_changed: Emitted when any export setting (frame range, crf, fps, output path) changes.
    """

    export_started = Signal()
    progress_changed = Signal(int, int)
    export_succeeded = Signal(Path)
    export_failed = Signal(str)
    export_cancelled = Signal()
    preview_ready = Signal(int, object)
    config_changed = Signal()

    def __init__(
        self,
        playback_controller: PlaybackController | None = None,
        view: VideoExportView | None = None,
        volume_controller: VolumeController | None = None,
        file_controller: FileController | None = None,
        *,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._playback_controller = playback_controller
        self._view = view
        self._volume_controller = volume_controller

        self._source_loaded: bool = playback_controller is not None and playback_controller.frame_count > 0
        self._total_frames: int = playback_controller.frame_count if playback_controller is not None else 0
        self._first_frame: int = 0
        self._last_frame: int = max(0, self._total_frames - 1)
        self._crf: int = 23

        # sets the effective speed of the video and estimates the final duration
        self._fps: int = int(playback_controller.speed) if playback_controller is not None else 24

        # the `window_size`` passed to Viewport.plotter.screenshot
        self._resolution = (1920, 1080)

        self._preset: str = "medium"
        self._output_path: Path | None = None

        self._is_exporting: bool = False
        self._is_cancelled: bool = False
        self._export_current_frame: int = 0
        self._writer: imageio.plugins.ffmpeg.FfmpegFormat.Writer | None = None

        self._pending_preview_frame: int | None = None

        # since we manipulated the underlying playback, we also store its state
        # to restore it later
        self._original_playback_frame: int | None = None
        self._original_playback_playing: bool | None = None
        self.store_playback_state()

        if file_controller is not None:
            file_controller.loaded.connect(self.set_source)
            file_controller.closed.connect(self.clear_source)

        if volume_controller is not None:
            volume_controller.volume_prepared.connect(self._on_volume_prepared)
            volume_controller.failed.connect(self._on_volume_failed)

    @property
    def total_frames(self) -> int:
        """Total number of frames available in the active recording."""
        return self._total_frames if self._source_loaded else 0

    @property
    def export_frame_count(self) -> int:
        """Number of frames included in the current export range."""
        if not self._source_loaded or self.total_frames == 0 or self._last_frame < self._first_frame:
            return 0
        return self._last_frame - self._first_frame + 1

    @property
    def first_frame(self) -> int:
        """0-based index of the first frame to export."""
        return self._first_frame

    @property
    def last_frame(self) -> int:
        """0-based index of the last frame to export (inclusive)."""
        return self._last_frame

    @property
    def crf(self) -> int:
        """Constant Rate Factor controlling video compression quality (0-51)."""
        return self._crf

    @property
    def fps(self) -> int:
        """Playback speed of the exported video in frames per second."""
        return self._fps

    @property
    def resolution(self) -> tuple[int, int]:
        """Width and height, in pixels, of exported frames."""
        return self._resolution

    @property
    def preset(self) -> str:
        """FFmpeg encoding preset for compression speed vs efficiency."""
        return self._preset

    @property
    def output_path(self) -> Path | None:
        """Current target output file path."""
        return self._output_path

    @property
    def is_exporting(self) -> bool:
        """Whether a video export task is currently active."""
        return self._is_exporting

    @property
    def is_available(self) -> bool:
        """Whether a recording is open and ready to be exported."""
        return self.total_frames > 0

    def store_playback_state(self) -> None:
        if self._playback_controller is not None:
            self._original_playback_frame = self._playback_controller.frame
            self._original_playback_playing = self._playback_controller.is_playing
            self._playback_controller.set_playing(False)

    def restore_playback(self) -> None:
        """Restore the playback position and state from before the dialog was opened."""

        if self._playback_controller is None:
            return

        if self._original_playback_frame is not None:
            self._playback_controller.go_to_frame(self._original_playback_frame)
        if self._original_playback_playing is not None:
            self._playback_controller.set_playing(self._original_playback_playing)

        self._original_playback_frame = None
        self._pending_preview_frame = None
        self._original_playback_playing = False

    def set_first_frame(self, frame: int) -> None:
        """Sets the start frame of the export range (0-based)."""

        frame = max(0, frame)
        if self._first_frame != frame:
            self._first_frame = frame
            self.config_changed.emit()

    def set_last_frame(self, frame: int) -> None:
        """Sets the end frame of the export range (0-based, inclusive)."""

        frame = min(self.total_frames - 1, max(0, frame)) if self.total_frames > 0 else max(0, frame)
        if self._last_frame != frame:
            self._last_frame = frame
            self.config_changed.emit()

    def set_frame_range(self, first: int, last: int) -> None:
        """Sets both first and last frames of the export range (0-based). Clamps them to proper valus."""

        first = max(0, first)
        last = min(self.total_frames - 1, max(0, last)) if self.total_frames > 0 else max(0, last)
        if self._first_frame != first or self._last_frame != last:
            self._first_frame = first
            self._last_frame = last
            self.config_changed.emit()

    def set_crf(self, crf: int) -> None:
        """Sets the Constant Rate Factor that affects quality of the video (clamped to [0, 51])."""

        crf = max(0, min(51, int(crf)))
        if self._crf != crf:
            self._crf = crf
            self.config_changed.emit()

    def set_fps(self, fps: int) -> None:
        """Sets export frames per second (minimum 1)."""
        fps = max(1, int(fps))
        if self._fps != fps:
            self._fps = fps
            self.config_changed.emit()

    def set_resolution(self, width: int, height: int) -> None:
        """Set the exported frame dimensions in pixels."""
        resolution = (max(1, int(width)), max(1, int(height)))
        if self._resolution != resolution:
            self._resolution = resolution
            self.config_changed.emit()

    def set_preset(self, preset: str) -> None:
        """Sets FFmpeg encoding preset."""

        preset = preset.strip().lower()
        if self._preset != preset:
            self._preset = preset
            self.config_changed.emit()

    def set_output_path(self, path: Path | str | None) -> None:
        """Sets target output file path."""
        p = Path(path) if path is not None else None
        if self._output_path != p:
            self._output_path = p
            self.config_changed.emit()

    def set_source(self, path: Path, source: FrameSource) -> None:
        """Updates controller configuration when a recording is loaded."""

        n_t = getattr(source.info, "n_t", 0)
        self._source_loaded = n_t > 0
        self._total_frames = n_t
        self._first_frame = 0
        self._last_frame = max(0, n_t - 1)

        # default output path next to source file
        self._output_path = path.with_name(f"{path.stem}_export.mp4")
        self.config_changed.emit()

    def clear_source(self) -> None:
        """Resets controller configuration when a recording is closed."""

        self._source_loaded = False
        self._total_frames = 0
        self._first_frame = 0
        self._last_frame = 0
        self._output_path = None
        self.config_changed.emit()

    def get_preview_frame(self, frame: int) -> NDArray | None:
        """
        Synchronously get the screenshot of the current viewport frame.

        Args:
            frame: Frame index to preview.

        Returns:
            NumPy RGB array if available, None otherwise.
        """

        if (
            self._playback_controller is not None
            and self._playback_controller.frame == frame
            and self._view is not None
        ):
            return self._view.screenshot(window_size=self._resolution)

        self.request_preview_frame(frame)  # go to frame
        return None

    def request_preview_frame(self, frame: int) -> None:
        """
        Navigates to `frame` and emit `preview_ready` when rendered.

        Args:
            frame: 0-based frame index.
        """

        if self._playback_controller is None or self._view is None:
            return

        if self._playback_controller.frame == frame:
            img = self._view.screenshot(window_size=self._resolution)
            self.preview_ready.emit(frame, img)
            return

        self._pending_preview_frame = frame
        self._playback_controller.go_to_frame(frame)

    def start_export(self) -> None:
        """Starts exporting the configured frame range to video."""

        if self._is_exporting:
            return

        if self.export_frame_count == 0:
            self.export_failed.emit("No frames to export.")
            return

        if self._output_path is None:
            self.export_failed.emit("Output path not set.")
            return  # the ui disables the "Export" button when the path is not selected

        self._is_exporting = True
        self._is_cancelled = False
        self.export_started.emit()
        self.progress_changed.emit(0, self.export_frame_count)  # start progress bar at 0

        self._output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._writer = imageio.get_writer(
                self._output_path,
                fps=self._fps,
                codec="libx264",
                pixelformat="yuv420p",
                macro_block_size=16,
                output_params=["-crf", str(self._crf), "-preset", self._preset],
            )
        except Exception as error:
            self._cleanup_export(remove_file=True)
            self.export_failed.emit(f"Failed to initialize video writer: {error}")
            return

        self._export_current_frame = self._first_frame
        self._request_next_export_frame()

    def cancel_export(self) -> None:
        """Cancels an ongoing export."""

        if self._is_exporting:
            self._is_cancelled = True
            self._cleanup_export(remove_file=True)
            self.export_cancelled.emit()

    def _request_next_export_frame(self) -> None:
        """Requests rendering of the current frame to export."""

        if self._is_cancelled or not self._is_exporting:
            return

        if self._export_current_frame > self._last_frame:
            self._finish_export()
            return

        frame = self._export_current_frame

        if self._playback_controller is not None:
            if self._playback_controller.frame != frame:
                self._playback_controller.go_to_frame(frame)  # updates the main view
                if self._volume_controller is None:
                    QTimer.singleShot(0, self._capture_and_advance)  # capture directly
                return
            else:  # already on the frame
                if (
                    self._volume_controller is None
                    or getattr(self._volume_controller, "_busy", False) is False
                ):
                    self._capture_and_advance()
                    return

        self._capture_and_advance()

    def _on_volume_prepared(self, prepared: object) -> None:
        """The VolumeController updated a frame, we must re-screenshot it"""

        frame_idx = getattr(prepared, "frame", None)  # extract signal payload

        if self._pending_preview_frame is not None and frame_idx == self._pending_preview_frame:
            self._pending_preview_frame = None
            if self._view is not None and not (
                self._is_exporting and frame_idx == self._export_current_frame
            ):
                img = self._view.screenshot(window_size=self._resolution)
                self.preview_ready.emit(frame_idx, img)

        if not self._is_exporting or self._is_cancelled:
            return

        if frame_idx == self._export_current_frame:
            self._capture_and_advance()

    def _on_volume_failed(self) -> None:
        """The VolumeController failed to load a frame"""

        if self._is_exporting:
            self._cleanup_export(remove_file=True)
            self.export_failed.emit(f"Failed to load frame {self._export_current_frame} from source.")

    def _capture_and_advance(self) -> None:
        """Captures screenshot for current frame, then writes to video."""

        if not self._is_exporting or self._is_cancelled:
            return

        try:
            if self._view is None:
                raise RuntimeError("No 3D view available to capture frame.")

            assert self._writer is not None, "Writer is created when export starts"
            image = self._view.screenshot(window_size=self._resolution)
            self._writer.append_data(image)
            self.preview_ready.emit(self._export_current_frame, image)

            done = self._export_current_frame - self._first_frame + 1  # increase frame
            self.progress_changed.emit(done, self.export_frame_count)

            self._export_current_frame += 1

            if self._export_current_frame > self._last_frame:
                self._finish_export()
            else:
                self._request_next_export_frame()
        except Exception as error:
            self._cleanup_export(remove_file=True)
            self.export_failed.emit(f"Error during video export: {error}")

    def _finish_export(self) -> None:
        """Closes the video writer"""

        path = self._output_path
        self._cleanup_export(remove_file=False)
        assert path is not None
        self.export_succeeded.emit(path)  # we are done

    def _cleanup_export(self, remove_file: bool = False) -> None:
        """Closes writer and reset export state."""

        self._is_exporting = False
        if self._writer is not None:
            with suppress(Exception):
                self._writer.close()
            self._writer = None

        if remove_file and self._output_path is not None:
            self._output_path.unlink(missing_ok=True)  # unlink removes the file
