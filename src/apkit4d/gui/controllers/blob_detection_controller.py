from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import pyvista as pv
from PySide6.QtCore import QObject, QTimer, Signal

from apkit4d.blob_detection import BlobParams, find_blobs
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FrameSource
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.views.widgets.blob_detection_inspector import BlobDetectionInspector
from apkit4d.visualization.data_mapper import create_blob_mesh


class BlobView(Protocol):
    """What the controller needs from the 3D view. `Viewport` provides it."""

    def show_blobs(self, poly: pv.PolyData) -> None: ...


@dataclass(frozen=True)
class _BlobDetection:
    frame: int
    blobs: pd.DataFrame


class BlobDetectionController(QObject):
    """
    Runs the blob detection on the frame that is shown and puts the result in the 3D view.

    The blob detection inspector only emits signals, so the controller keeps the current
    parameters. Detection runs when the user presses "Find blobs", or on every change
    of frame or parameter if "update on change" is on. Only one detection runs at a time,
    and a result is shown only if it still belongs to the recording and the frame
    that are on screen.

    Args:
        inspector: The view with the parameters and the "Find blobs" button.
        view: The 3D view where the blobs are shown.
        parent: Qt parent, so the controller lives as long as its owner.

    Signals:
        params_changed: Emitted when BlobParams properties are changed from the view
    """

    # used to debounce properties changes
    DEBOUNCE_MS = 300

    params_changed = Signal(str, float)

    def __init__(
        self,
        inspector: BlobDetectionInspector,
        view: BlobView,
        parent: QObject | None = None,
    ):
        super().__init__(parent)
        self._inspector = inspector
        self._view = view

        self._params = BlobParams()

        # set default inspector parameters
        self._inspector.diameter_xy = self._params.diameter_xy_um
        self._inspector.diameter_z = self._params.diameter_z_um
        self._inspector.lo_g_threshold = self._params.threshold
        self._inspector.seed_separation = self._params.split
        self._inspector.boundary = self._params.grow_frac
        self._inspector.min_volume = self._params.min_volume_um3
        self._inspector.max_volume = self._params.max_volume_um3
        self._inspector.z_equals_xy = False
        self._inspector.update_on_change = False

        # connect inspector signals
        self._inspector.diameter_xy_changed.connect(lambda v: self._on_param_changed("diameter_xy_um", v))
        self._inspector.diameter_z_changed.connect(lambda v: self._on_param_changed("diameter_z_um", v))
        self._inspector.lo_g_changed.connect(lambda v: self._on_param_changed("threshold", v))
        self._inspector.seed_separation_changed.connect(lambda v: self._on_param_changed("split", v))
        self._inspector.boundary_changed.connect(lambda v: self._on_param_changed("grow_frac", v))
        self._inspector.min_volume_changed.connect(lambda v: self._on_param_changed("min_volume_um3", v))
        self._inspector.max_volume_changed.connect(lambda v: self._on_param_changed("max_volume_um3", v))
        self._inspector.diameter_z_equal_to_xy_toggled.connect(self._on_z_equals_xy)
        self._inspector.update_on_change_toggled.connect(self._on_update_on_change)
        self._inspector.show_segments_toggled.connect(self._on_show_segments_toggled)
        self._inspector.find_blob_clicked.connect(self._detect)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(self.DEBOUNCE_MS)
        self._timer.timeout.connect(self._detect)

        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_done)
        self._runner.failed.connect(self._on_failed)

        self._source: FrameSource | None = None
        self._frame = 0
        self._generation = 0  # grows with every recording, to ignore what comes from an old one
        self._busy = False  # True when a detection is running
        self._stale = False  # True if a new run was requested while one was running
        self._running = (0, 0)  # (generation, frame) the running detection was started for

    def set_source(self, _path: Path, source: FrameSource):
        """Start working on a new recording."""
        self._generation += 1
        self._source = source
        self._stale = False
        self._frame = 0
        self._timer.stop()
        self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)

    def clear_source(self):
        """The recording was closed."""
        self._generation += 1
        self._source = None
        self._frame = 0
        self._stale = False
        self._timer.stop()
        self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)

    def on_set_frame(self, frame: int):
        """The frame shown changed."""
        self._frame = frame

        if self._inspector.update_on_change:
            self._detect()
        else:
            self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)

    def _on_param_changed(self, field: str, value: float):
        self._params = replace(self._params, **{field: value})

        if self._inspector.update_on_change:
            self._schedule_a_detect()

        self.params_changed.emit(field, value)

    def _on_z_equals_xy(self, _enabled: bool):
        if self._inspector.update_on_change:
            self._schedule_a_detect()

    def _on_update_on_change(self, enabled: bool):
        if enabled:
            self._schedule_a_detect()

    def _schedule_a_detect(self):
        self._timer.start()

    def _detect(self):
        self._timer.stop()

        if self._source is None:
            return

        if self._busy:
            self._stale = True  # run again with the latest values when this one ends
            return

        self._busy = True
        self._stale = False
        self._running = (self._generation, self._frame)
        self._inspector.set_detection_status(texts.INSPECTOR_STATUS_DETECTING)
        self._runner.run(partial(self._detect_blobs, self._source, self._frame, self._params))

    def _detect_blobs(self, source: FrameSource, frame: int, params: BlobParams) -> _BlobDetection:
        """Runs in the worker thread: read, preprocess, detect."""

        raw_volume = source.read(frame)

        blobs, _labels, _seeds = find_blobs(
            raw_volume,  # TODO: pass preprocessed volume instead of the raw one
            params,
            source.info.voxel,
            offset=(0, 0, 0),  # TODO: set the offset based on the ROI
            intensity=raw_volume,  # TODO: pass raw_volume[z0:z1, y0:y1, x0:x1] based on the ROI
            frame=frame,
        )

        return _BlobDetection(frame, blobs)

    def _on_done(self, _task_id: int, result: _BlobDetection):
        if self._finish():
            self._show_blobs(result)

        self._run_again_if_needed()

    def _on_failed(self, _task_id: int, error: Exception):
        if self._finish():
            reason = str(error) or type(error).__name__
            self._clear_blobs(texts.INSPECTOR_STATUS_DETECTION_FAILED.format(reason=reason))

        self._run_again_if_needed()

    def _finish(self) -> bool:
        """
        Close the running detection.

        Returns:
            True if its result is still worth showing.
        """

        self._busy = False
        return self._running == (self._generation, self._frame) and not self._stale

    def _run_again_if_needed(self):
        if self._stale:
            self._detect()

    def _show_blobs(self, result: _BlobDetection):
        blobs = result.blobs
        display_frame = result.frame + 1

        if blobs.empty:
            self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS_FOUND.format(frame=display_frame))
            return

        self._view.show_blobs(create_blob_mesh(blobs))
        self._inspector.set_detection_status(
            texts.INSPECTOR_STATUS_BLOBS_FOUND.format(
                frame=display_frame,
                count=len(blobs),
                volume=float(np.median(blobs["volume_um3"])),
            )
        )

    def _clear_blobs(self, status: str):
        self._view.show_blobs(pv.PolyData())  # an empty mesh removes the blobs
        self._inspector.set_detection_status(status)

    def _on_show_segments_toggled(self, toggled: bool):
        if toggled:
            # TODO: show segments
            pass
        else:
            # TODO: clear segments
            pass
