"""
Controller of the 3D view: shows the frames of the open recording.

The frame is read in a background thread, because reading takes time. Then it is mapped to a grid and
shown in the GUI thread, because the 3D view can only be used from there. Only one frame is read at a
time and only the frame wanted most recently is shown: when frames are requested faster than they are
read (dragging the slider, fast playback), the ones in between are skipped.

How a frame is handled:
1. read it from disk
2. extract the ROI
3. preprocess it
4. create_volume_grid to display
"""

import math
from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Protocol, runtime_checkable

import numpy as np
import pyvista as pv
from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FrameSource
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.image import Image
from apkit4d.preprocessing import PreprocParams, preprocess
from apkit4d.roi import Bounds6D, RegionOfInterest
from apkit4d.visualization.data_mapper import create_volume_grid


class VolumeView(Protocol):
    """What the controller needs from the 3D view. `Viewport` provides it."""

    def show_volume(self, grid: pv.ImageData, reset_camera: bool = True) -> None: ...


class _SignalLike(Protocol):
    def connect(self, slot: Callable[..., object]) -> object: ...


@runtime_checkable
class RoiSelectionView(Protocol):
    """Optional interactive ROI selection contract provided by `Viewport`."""

    @property
    def roi_updated(self) -> _SignalLike: ...

    def start_roi_selection(self) -> None: ...

    def set_roi_preview(self, roi: RegionOfInterest) -> None: ...

    def accept_roi_selection(self) -> RegionOfInterest | None: ...

    def cancel_roi_selection(self) -> None: ...


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

    volume_bounds_changed = Signal(object)

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

        self._roi: RegionOfInterest | None = None
        self._current_frame: int = 0

        # the unaltered raw volume read from the CZI
        self._current_full_volume: Image[np.uint16] | None = None

        # the volume obtained via taking the ROI from the full volume
        self._current_roi_volume: Image[np.uint16] | None = None

        # origin of the roi, None = (0, 0, 0)
        self._current_roi_origin: tuple[float, float, float] | None = None

        self._preproc_params = PreprocParams()
        self._preproc_busy = False
        self._preproc_pending = False
        self._preproc_runner = TaskRunner(self)
        self._preproc_runner.succeeded.connect(self._on_preproc_done)
        self._preproc_runner.failed.connect(self._on_preproc_failed)

    @property
    def preproc_params(self) -> PreprocParams:
        """The currently applied preprocessing parameters, or None if showing raw volume."""
        return self._preproc_params

    def apply_preproc_params(self, params: PreprocParams) -> None:
        """
        Apply preprocessing parameters to the current ROI-cropped volume and update the 3D view.

        Args:
            params: The preprocessing parameters to apply, or None to show the raw ROI volume.
        """

        self._preproc_params = params
        if self._current_roi_volume is None or not self._usable:
            return

        if self._preproc_busy:
            self._preproc_pending = True
            return

        self._start_preprocessing(self._current_roi_volume, params)

    def _start_preprocessing(self, roi_volume: NDArray, params: PreprocParams) -> None:
        self._preproc_busy = True
        self._preproc_runner.run(partial(preprocess, roi_volume, params, self._voxel))

    def _on_preproc_done(self, _task_id: int, volume: NDArray) -> None:
        self._preproc_busy = False

        if self._preproc_pending:
            self._preproc_pending = False
            if self._current_roi_volume is not None and self._usable:
                self._start_preprocessing(self._current_roi_volume, self._preproc_params)
                return

        if self._usable:
            self._show(self._current_frame, volume, self._current_roi_origin)

    def _on_preproc_failed(self, _task_id: int, error: Exception) -> None:
        self._preproc_busy = False
        self._preproc_pending = False
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
        self._roi = None
        self._current_full_volume = None
        self._current_roi_volume = None
        self._current_roi_origin = None
        self._first_frame = True
        self._wanted = None
        self._current_frame = 0
        self._preproc_pending = False
        self._usable = self._has_valid_voxel(source)
        if self._usable:
            # when we read the file we set the bounds so that the ROI inspector can show them
            sz, sy, sx = self._voxel
            bounds: Bounds6D = (
                0.0,
                max(0, source.info.n_x - 1) * sx,
                0.0,
                max(0, source.info.n_y - 1) * sy,
                0.0,
                max(0, source.info.n_z - 1) * sz,
            )
            self.volume_bounds_changed.emit(bounds)
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
            self._current_frame = frame
            self._current_full_volume = volume
            self._apply_roi_and_show(volume)
        self._read_the_next_frame()

    def _apply_roi_and_show(self, full_volume: Image[np.uint16]) -> None:
        """Extract the ROI slice from `full_volume`, then preprocess or display it"""

        roi_volume, roi_origin = self._extract_roi(full_volume)
        self._current_roi_volume = roi_volume
        self._current_roi_origin = roi_origin
        if self._preproc_busy:
            self._preproc_pending = True
        else:
            self._start_preprocessing(roi_volume, self._preproc_params)

    def _extract_roi(self, volume: NDArray) -> tuple[NDArray, tuple[float, float, float] | None]:
        if self._roi is not None:
            sub_vol, sub_origin = self._roi.extract_subvolume(volume, self._voxel)
            return sub_vol, sub_origin
        return volume, None

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

    def _show(
        self,
        frame: int,
        volume: Image[np.uint16],
        origin: tuple[float, float, float] | None,
    ) -> None:
        """Builds a PyVista grid from `volume` and hand gives it to the view"""

        if volume.ndim != 3:
            self._fail(texts.STATUS_NOT_3D.format(frame=frame, shape=volume.shape))
            return

        grid = create_volume_grid(volume, self._voxel, (0, 0, 0) if origin is None else origin)
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

    @property
    def roi(self) -> RegionOfInterest | None:
        """Currently active RegionOfInterest used to crop displayed frames, or None for full volume."""
        return self._roi

    def set_roi(self, roi: RegionOfInterest | None) -> None:
        """
        Apply or clear the active RegionOfInterest and immediately refresh the current frame.

        Re-extracts the ROI from the cached full volume so no disk read is needed.
        If preprocessing is active it is re-triggered on the new cropped volume.
        """

        self._roi = roi
        if self._current_full_volume is None or not self._usable:
            return
        self._apply_roi_and_show(self._current_full_volume)
