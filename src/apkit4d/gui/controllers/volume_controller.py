"""
Controller of the 3D view: shows the frames of the open recording.

The frame is read in a background thread, because reading takes time. Then it is mapped to a grid and
shown in the GUI thread, because the 3D view can only be used from there. Only one frame is read at a
time and only the frame wanted most recently is shown: when frames are requested faster than they are
read (dragging the slider, fast playback), the ones in between are skipped.
"""

import math
from functools import partial
from pathlib import Path
from typing import Protocol

import pyvista as pv
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FrameSource
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.preprocessing import PreprocParams, preprocess
from apkit4d.visualization.data_mapper import create_volume_grid


class VolumeView(Protocol):
    """What the controller needs from the 3D view. `Viewport` provides it."""

    def show_volume(self, grid: pv.ImageData, reset_camera: bool = True) -> None: ...


class VolumeController(QObject):
    """
    Reads the frames of the open recording and shows them in the 3D view.

    Whatever is wrong with a recording that the 3D view cannot show (a frame that cannot be read, a
    volume that is not 3D, a voxel size that is not valid) is reported in the status bar, because the
    3D view would otherwise just stay empty.

    Args:
        window: The view where the problems are reported.
        view: The 3D view.
        parent: Qt parent, so the controller lives as long as its owner.

    Signals:
        failed: Emitted when a frame could not be shown, so that the playback can stop.
    """

    failed = Signal()

    def __init__(self, window: MainWindow, view: VolumeView, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._view = view
        self._source: FrameSource | None = None
        self._voxel = (1.0, 1.0, 1.0)  # size of the voxels of the recording, in micrometers
        self._usable = False  # False if the recording cannot be shown at all
        self._generation = 0  # grows with every recording, to ignore what comes from an old one
        self._first_frame = True  # the camera is reset only for the first frame of a recording
        self._wanted: int | None = None  # the frame to read next, if one was requested meanwhile
        self._busy = False
        self._loading = (0, 0)  # generation and frame that are being read

        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_read)
        self._runner.failed.connect(self._on_read_failed)

        self._current_frame: int = 0
        self._current_raw_volume: NDArray | None = None
        self._preproc_params: PreprocParams | None = None
        self._preproc_busy = False
        self._preproc_wanted: PreprocParams | None = None
        self._preproc_runner = TaskRunner(self)
        self._preproc_runner.succeeded.connect(self._on_preproc_done)
        self._preproc_runner.failed.connect(self._on_preproc_failed)

    @property
    def preproc_params(self) -> PreprocParams | None:
        """The currently applied preprocessing parameters, or None if showing raw volume."""
        return self._preproc_params

    def apply_preproc_params(self, params: PreprocParams | None) -> None:
        """
        Apply preprocessing parameters to the current volume and update the 3D view.

        Args:
            params: The preprocessing parameters to apply, or None to show raw volume.
        """
        self._preproc_params = params
        if self._current_raw_volume is None or not self._usable:
            return

        if params is None:
            self._show(self._current_frame, self._current_raw_volume)
            return

        if self._preproc_busy:
            self._preproc_wanted = params
            return

        self._start_preprocessing(self._current_raw_volume, params)

    def _start_preprocessing(self, volume: NDArray, params: PreprocParams) -> None:
        self._preproc_busy = True
        self._preproc_runner.run(partial(preprocess, volume, params, self._voxel))

    def _on_preproc_done(self, _task_id: int, volume: NDArray) -> None:
        self._preproc_busy = False
        if self._usable:
            self._show(self._current_frame, volume)
        if self._preproc_wanted is not None:
            wanted = self._preproc_wanted
            self._preproc_wanted = None
            if self._current_raw_volume is not None:
                self._start_preprocessing(self._current_raw_volume, wanted)

    def _on_preproc_failed(self, _task_id: int, error: Exception) -> None:
        self._preproc_busy = False
        self._preproc_wanted = None
        reason = str(error) or type(error).__name__
        self._window.set_status(f"Preprocessing failed: {reason}")

    def set_source(self, _path: Path, source: FrameSource) -> None:
        """
        Start showing a recording, from its first frame.

        Args:
            _path: Path of the file, which the signal that calls this method also carries.
            source: The open recording.
        """
        self._generation += 1
        self._source = source
        self._voxel = source.info.voxel
        self._first_frame = True
        self._wanted = None
        self._current_frame = 0
        self._current_raw_volume = None
        self._preproc_wanted = None
        self._usable = self._has_valid_voxel(source)
        if self._usable:
            self.show_frame(0)

    def show_frame(self, frame: int) -> None:
        """
        Show `frame` as soon as it has been read. Does nothing if there is no recording to show.

        Args:
            frame: Index of the frame, starting from 0.
        """
        source = self._source
        if source is None or not self._usable:
            return
        if self._busy:
            # the frame that is being read may be the one wanted, otherwise it is read afterwards
            self._wanted = None if self._loading == (self._generation, frame) else frame
            return
        self._start_reading(source, frame)

    def _start_reading(self, source: FrameSource, frame: int) -> None:
        self._busy = True
        self._loading = (self._generation, frame)
        self._runner.run(partial(source.read, frame))

    def _on_read(self, _task_id: int, volume: NDArray) -> None:
        generation, frame = self._finish_reading()
        if generation == self._generation:
            # FIXME: see what the PipelineController does, move it there
            self._current_frame = frame
            self._current_raw_volume = volume
            if self._preproc_params is not None:
                self._start_preprocessing(volume, self._preproc_params)
            else:
                self._show(frame, volume)
        self._read_the_next_frame()

    def _on_read_failed(self, _task_id: int, error: Exception) -> None:
        generation, frame = self._finish_reading()
        if generation == self._generation:
            reason = str(error) or type(error).__name__
            self._fail(texts.STATUS_FRAME_FAILED.format(frame=frame, reason=reason))
        self._read_the_next_frame()

    def _finish_reading(self) -> tuple[int, int]:
        self._busy = False
        return self._loading

    def _read_the_next_frame(self) -> None:
        if self._wanted is None or self._source is None:
            return
        frame, self._wanted = self._wanted, None
        self._start_reading(self._source, frame)

    def _show(self, frame: int, volume: NDArray) -> None:
        if volume.ndim != 3:
            self._fail(texts.STATUS_NOT_3D.format(frame=frame, shape=volume.shape))
            return
        grid = create_volume_grid(volume, self._voxel)
        if grid.n_points == 0:
            self._fail(texts.STATUS_EMPTY_VOLUME.format(frame=frame))
            return
        self._view.show_volume(grid, reset_camera=self._first_frame)
        self._first_frame = False

    def _fail(self, message: str) -> None:
        self._wanted = None
        self._window.set_status(message)
        self.failed.emit()

    def _has_valid_voxel(self, source: FrameSource) -> bool:
        voxel = source.info.voxel
        if all(math.isfinite(size) and size > 0 for size in voxel):
            return True
        name = Path(source.info.path).name
        self._window.set_status(texts.STATUS_INVALID_VOXEL.format(name=name, voxel=voxel))
        return False
