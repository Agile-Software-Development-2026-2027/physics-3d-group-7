from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path
from typing import Protocol

import numpy as np
import pandas as pd
import pyvista as pv
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from apkit4d.blob_detection import BlobParams, find_blobs
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FrameSource
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.volume_controller import PreparedVolume
from apkit4d.gui.views.widgets.blob_detection_inspector import BlobDetectionInspector
from apkit4d.visualization.data_mapper import create_blob_mesh


class BlobView(Protocol):
    """What the controller needs from the 3D view. `Viewport` provides it."""

    def show_blobs(self, poly: pv.PolyData) -> None: ...


@dataclass(frozen=True)
class BlobDetection:
    frame: int
    blobs: pd.DataFrame


def detect_blobs(prepared: PreparedVolume, params: BlobParams) -> BlobDetection:
    """Runs in the worker thread: only the detection, the volume is already prepared."""

    blobs, _labels, _seeds = find_blobs(
        prepared.image,
        params,
        prepared.voxel,
        intensity=prepared.roi_volume,
        offset=prepared.offset,
        frame=prepared.frame,
    )

    return BlobDetection(prepared.frame, blobs)


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
        self._inspector.diameter_xy_changed.connect(
            lambda v: self._on_blob_param_changed("diameter_xy_um", v)
        )
        self._inspector.diameter_z_changed.connect(lambda v: self._on_blob_param_changed("diameter_z_um", v))
        self._inspector.lo_g_changed.connect(lambda v: self._on_blob_param_changed("threshold", v))
        self._inspector.seed_separation_changed.connect(lambda v: self._on_blob_param_changed("split", v))
        self._inspector.boundary_changed.connect(lambda v: self._on_blob_param_changed("grow_frac", v))
        self._inspector.min_volume_changed.connect(lambda v: self._on_blob_param_changed("min_volume_um3", v))
        self._inspector.max_volume_changed.connect(lambda v: self._on_blob_param_changed("max_volume_um3", v))
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

        self._prepared: PreparedVolume | None = None  # the volume on screen
        self._busy = False  # True when a detection is running
        self._stale = False  # True if a new run was requested while one was running
        self._running: PreparedVolume | None = None  # the volume the running detection works on
        self._precomputed_by_frame: dict[int, pd.DataFrame] | None = None

    @Slot(bool)
    def on_normalization_toggled(self, checked: bool):
        disabled = not checked

        self._inspector.disable_update_on_change(disabled)
        if disabled:
            self._inspector.update_on_change = False

        self._inspector.disable_find_blob(disabled)

    @Slot(PreparedVolume)
    def on_volume_prepared(self, prepared: PreparedVolume):
        """The 3D view shows a new volume (frame, ROI or preprocessing changed)."""

        if prepared is self._prepared:
            return

        self._prepared = prepared

        live = self._inspector.update_on_change
        if live:
            # the blobs on screen belong to the previous volume
            self._clear_blobs(texts.INSPECTOR_STATUS_DETECTING)
            self._detect()
        elif self._precomputed_by_frame is not None:
            self._show_precomputed_frame(prepared.frame)
        else:
            self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)

    def set_precomputed_blobs(self, blobs_df: pd.DataFrame | None) -> None:
        """Load precomputed per-frame blobs (e.g. from mock or processed data)."""
        self._timer.stop()
        if blobs_df is None or blobs_df.empty:
            self._precomputed_by_frame = None
            self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)
            return

        by_frame: dict[int, pd.DataFrame] = {}
        for _frame_key, group in blobs_df.groupby("frame", sort=False):
            frame_num = int(group["frame"].iloc[0])
            by_frame[frame_num] = group.reset_index(drop=True)
        self._precomputed_by_frame = by_frame
        current_frame = self._prepared.frame if self._prepared is not None else 0
        self._show_precomputed_frame(current_frame)

    def _show_precomputed_frame(self, frame: int) -> None:
        if self._precomputed_by_frame is None:
            return
        frame_df = self._precomputed_by_frame.get(frame, pd.DataFrame())
        self._show_blobs(BlobDetection(frame, frame_df))

    def set_source(self, _path: Path, _source: FrameSource):
        """A new recording was opened: forget the volume of the previous one."""
        self._reset()

    def clear_source(self):
        """The recording was closed."""
        self._reset()

    def _reset(self):
        self._prepared = None
        self._precomputed_by_frame = None
        self._stale = False
        self._timer.stop()
        self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)

    @Slot(str, float)
    def _on_blob_param_changed(self, field: str, value: float):
        self._params = replace(self._params, **{field: value})

        if self._inspector.update_on_change:
            self._schedule_a_detect()

        self.params_changed.emit(field, value)

    @Slot(bool)
    def _on_update_on_change(self, enabled: bool):
        if enabled:
            self._schedule_a_detect()

    def _schedule_a_detect(self):
        self._timer.start()

    def _detect(self):
        self._timer.stop()

        prepared = self._prepared
        if prepared is None or not prepared.is_image_normalized:
            return  # no volume on screen yet or volume is not normalized

        if self._busy:
            self._stale = True  # run again with the latest values when this one ends
            return

        self._busy = True
        self._stale = False
        self._running = prepared
        self._inspector.set_detection_status(texts.INSPECTOR_STATUS_DETECTING)
        self._runner.run(partial(detect_blobs, prepared, self._params))

    @Slot(int, BlobDetection)
    def _on_done(self, _task_id: int, result: BlobDetection):
        if self._finish():
            self._show_blobs(result)

        self._run_again_if_needed()

    @Slot(int, Exception)
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
        # a new frame, ROI, preprocessing or recording always produce a new PreparedVolume
        return self._running is self._prepared and not self._stale

    def _run_again_if_needed(self):
        if self._stale:
            self._detect()

    def _show_blobs(self, result: BlobDetection):
        blobs = result.blobs
        display_frame = result.frame + 1

        if blobs.empty:
            self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS_FOUND.format(frame=display_frame))
            return

        median_vol = float(np.median(blobs["volume_um3"])) if "volume_um3" in blobs.columns else 0.0
        self._view.show_blobs(create_blob_mesh(blobs))
        self._inspector.set_detection_status(
            texts.INSPECTOR_STATUS_BLOBS_FOUND.format(
                frame=display_frame,
                count=len(blobs),
                volume=median_vol,
            )
        )

    def _clear_blobs(self, status: str):
        self._view.show_blobs(pv.PolyData())  # an empty mesh removes the blobs
        self._inspector.set_detection_status(status)

    @Slot(bool)
    def _on_show_segments_toggled(self, toggled: bool):
        if toggled:
            # TODO: show segments
            pass
        else:
            # TODO: clear segments
            pass
