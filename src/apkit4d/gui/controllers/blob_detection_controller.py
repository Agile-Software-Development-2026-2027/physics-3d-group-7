import logging
from dataclasses import dataclass, field, replace
from functools import partial
from pathlib import Path
from typing import Protocol, cast

import numpy as np
import pandas as pd
import pyvista as pv
from numpy.typing import NDArray
from PySide6.QtCore import QObject, QTimer, Signal, Slot

from apkit4d.core.roi import RegionOfInterest
from apkit4d.detection.blob_detection import BlobParams
from apkit4d.detection.preprocessing import PreprocParams
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.trajectory_detection import DetectionData, detect_sequence
from apkit4d.gui.controllers.volume_controller import PreparedVolume, VolumeController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep, StepStatus
from apkit4d.gui.views.stages.blob_detection_inspector import BlobDetectionInspector
from apkit4d.io.czi import CziSource
from apkit4d.pipeline.contracts import CroppedFrame, PreprocessedFrame
from apkit4d.pipeline.frame_stages import detect_blobs_in_frame
from apkit4d.visualization.data_mapper import create_blob_mesh

logger = logging.getLogger(__name__)


class BlobView(Protocol):
    """What the controller needs from the 3D view. `Viewport` provides it."""

    def show_blobs(self, poly: pv.PolyData) -> None: ...


@dataclass(frozen=True)
class BlobDetection:
    frame: int
    blobs: pd.DataFrame
    seeds_response: NDArray = field(default_factory=lambda: np.empty(0, dtype=np.float32))


def detect_blobs(prepared: PreparedVolume, params: BlobParams) -> BlobDetection:
    """Runs in the worker thread: only the detection, the volume is already prepared."""
    cropped = CroppedFrame(
        frame=prepared.frame,
        raw_roi_volume=prepared.roi_volume,
        voxel_um=prepared.voxel,
        origin_xyz_um=(
            prepared.offset[2] * prepared.voxel[2],
            prepared.offset[1] * prepared.voxel[1],
            prepared.offset[0] * prepared.voxel[0],
        ),
        voxel_offset_zyx=prepared.offset,
    )
    preproc = PreprocessedFrame(
        cropped=cropped,
        image=prepared.image,
        params=PreprocParams(normalization_enabled=prepared.is_image_normalized),
    )
    result = detect_blobs_in_frame(
        preproc,
        params,
        include_time=False,
        require_normalized=True,
    )
    return BlobDetection(result.frame, result.detections, result.seeds_response)


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
        seeds_response_changed: seeds_response_changed: Emitted with the LoG response of the
                                candidates of a detection, or None when the recording changes.
    """

    # used to debounce properties changes
    DEBOUNCE_MS = 300

    params_changed = Signal(str, float)
    seeds_response_changed = Signal(object)  # NDArray, or None when there is nothing to show

    def __init__(
        self,
        inspector: BlobDetectionInspector,
        view: BlobView | None = None,
        parent: QObject | None = None,
        *,
        pipeline_model: PipelineModel | None = None,
        pipeline_controller: PipelineController | None = None,
        file_controller: FileController | None = None,
        volume_controller: VolumeController | None = None,
    ):
        super().__init__(parent)
        self._inspector = inspector
        self._view = view
        self._pipeline_model = pipeline_model
        self._pipeline_controller = pipeline_controller
        self._file_controller = file_controller
        self._volume_controller = volume_controller

        self._params = (
            BlobParams.from_dict(pipeline_model.get_step_params(PipelineStep.DETECTION))
            if pipeline_model is not None
            else BlobParams()
        )

        # set default inspector parameters
        self._inspector.set_params(self._params)
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

        self._detection_runner = TaskRunner(self)
        self._detection_runner.succeeded.connect(self._on_detection_ready)
        self._detection_runner.failed.connect(self._on_detection_failed)
        self._detection_task: int | None = None
        self._detection_generation = 0
        self._detection_running_generation: int | None = None
        self._detection_running_source: FrameSource | None = None
        self._detection_running_params: tuple[PreprocParams, BlobParams, RegionOfInterest | None] | None = (
            None
        )

        if self._pipeline_model is not None:
            self._pipeline_model.pipeline_reset.connect(self._on_detection_pipeline_reset)
            self._pipeline_model.step_status_changed.connect(self._on_detection_step_status_changed)
            self._pipeline_model.step_params_changed.connect(self._on_step_params_changed)
        if self._pipeline_controller is not None:
            self._pipeline_controller.set_stage_runner(
                PipelineStep.DETECTION,
                self._start_detection_if_needed,
            )

        self._prepared: PreparedVolume | None = None  # the volume on screen
        self._busy = False  # True when a detection is running
        self._stale = False  # True if a new run was requested while one was running
        self._running: PreparedVolume | None = None  # the volume the running detection works on
        self._precomputed_by_frame: dict[int, pd.DataFrame] | None = None

    @property
    def params(self) -> BlobParams:
        """Current blob detection parameters."""
        return self._params

    def set_params(self, params: BlobParams) -> None:
        """Synchronize controller and inspector widgets from `params` without emitting signals."""
        self._params = params
        self._inspector.set_params(params)

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
        if "response" in frame_df.columns and not frame_df.empty:
            seeds = frame_df["response"].dropna().to_numpy(dtype=np.float32)
        else:
            seeds = np.empty(0, dtype=np.float32)
        self._show_blobs(BlobDetection(frame, frame_df, seeds))

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
        self._detection_generation += 1
        self._timer.stop()
        self.seeds_response_changed.emit(None)
        self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS)

    def _on_step_params_changed(self, step: PipelineStep) -> None:
        if step != PipelineStep.DETECTION or self._pipeline_model is None:
            return
        model_params = BlobParams.from_dict(self._pipeline_model.get_step_params(PipelineStep.DETECTION))
        if model_params != self._params:
            self.set_params(model_params)

    def _detection_params(self) -> tuple[PreprocParams, BlobParams, RegionOfInterest | None]:
        """Take a snapshot of the Stage 3 sequence detection parameters."""
        assert self._pipeline_model is not None
        roi = self._volume_controller.roi if self._volume_controller is not None else None
        if self._volume_controller is None:
            roi_dict = self._pipeline_model.get_step_params(PipelineStep.ROI)
            roi = RegionOfInterest.from_dict(roi_dict) if roi_dict else None

        return (
            self._pipeline_model.get_preproc_params(),
            BlobParams.from_dict(self._pipeline_model.get_step_params(PipelineStep.DETECTION)),
            roi,
        )

    def _on_detection_step_status_changed(self, step: PipelineStep, status: StepStatus) -> None:
        if step != PipelineStep.DETECTION:
            return
        if status == StepStatus.RUNNING:
            if self._pipeline_controller is None:
                self._start_detection_if_needed()
        else:
            self._detection_generation += 1

    def _on_detection_pipeline_reset(self) -> None:
        self._detection_generation += 1
        if self._precomputed_by_frame is not None:
            self.set_precomputed_blobs(None)

    def _start_detection_if_needed(self) -> None:
        """Compute detections across the full recording using the open source."""
        if self._pipeline_model is None or self._pipeline_controller is None:
            return
        if (
            self._pipeline_model.get_status(PipelineStep.DETECTION) != StepStatus.RUNNING
            or self._detection_task is not None
        ):
            return

        if self._pipeline_model.batch_results is not None:
            detections, _metadata = self._pipeline_model.batch_results
            if self._precomputed_by_frame is None and not detections.empty:
                self.set_precomputed_blobs(detections)
            self._pipeline_controller.complete_stage(PipelineStep.DETECTION)
            return

        try:
            source = self._file_controller.source if self._file_controller is not None else None
            if source is None:
                raise ValueError("Open a CZI file before running detection.")

            params = self._detection_params()
            self._detection_running_source = source
            self._detection_running_params = params
            self._detection_running_generation = self._detection_generation

            preproc, blob, roi = params
            self._detection_task = self._detection_runner.run(
                partial(
                    detect_sequence,
                    cast(CziSource, source),
                    preproc,
                    blob,
                    roi,
                )
            )
            logger.debug("Started Stage 3 sequence detection (generation=%d)", self._detection_generation)
        except Exception as error:
            self._report_detection_failure(error)

    def _detection_result_is_current(self) -> bool:
        if self._pipeline_model is None or self._file_controller is None:
            return False
        return (
            self._detection_running_generation == self._detection_generation
            and self._pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.RUNNING
            and self._file_controller.source is self._detection_running_source
            and self._detection_running_params == self._detection_params()
        )

    def _on_detection_ready(self, task_id: int, result: object) -> None:
        if task_id != self._detection_task:
            return

        self._detection_task = None
        if not self._detection_result_is_current():
            self._start_detection_if_needed()
            return

        if not isinstance(result, DetectionData):
            self._report_detection_failure(TypeError("Detection returned an unexpected result."))
            return

        assert self._pipeline_model is not None
        assert self._pipeline_controller is not None
        self._pipeline_model.set_batch_results(result.detections, result.metadata)
        self.set_precomputed_blobs(result.detections)
        self._pipeline_controller.complete_stage(PipelineStep.DETECTION)
        logger.info("Completed Stage 3 sequence detection (%d detections)", len(result.detections))

    def _on_detection_failed(self, task_id: int, error: object) -> None:
        if task_id != self._detection_task:
            return

        self._detection_task = None
        if not self._detection_result_is_current():
            self._start_detection_if_needed()
            return

        self._report_detection_failure(error)

    def _report_detection_failure(self, error: object) -> None:
        if self._pipeline_model is None or self._pipeline_controller is None:
            return
        self._pipeline_model.invalidate_from(PipelineStep.DETECTION)
        reason = str(error) or type(error).__name__
        self._pipeline_controller.report_stage_failure("Blob detection failed", reason)
        logger.warning("Stage 3 sequence detection failed: %s", reason)

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

        self.seeds_response_changed.emit(result.seeds_response)

        if blobs.empty:
            self._clear_blobs(texts.INSPECTOR_STATUS_NO_BLOBS_FOUND.format(frame=display_frame))
            return

        median_vol = float(np.median(blobs["volume_um3"])) if "volume_um3" in blobs.columns else 0.0
        if self._view is not None:
            self._view.show_blobs(create_blob_mesh(blobs))
        self._inspector.set_detection_status(
            texts.INSPECTOR_STATUS_BLOBS_FOUND.format(
                frame=display_frame,
                count=len(blobs),
                volume=median_vol,
            )
        )

    def _clear_blobs(self, status: str):
        if self._view is not None:
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
