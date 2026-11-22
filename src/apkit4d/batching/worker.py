"""Worker-level frame detection, ROI extraction, and process resource management.

This module provides the core per-frame blob detection pipeline and worker task functions
executed across parallel processes.

RefactorNote:
    Refactored `batch.py`.
    And yeah apparently they tought about making some sort of worker system, pretty sus.
"""

from pathlib import Path
from typing import Any, Final

import pandas as pd
import psutil

from apkit4d.core.models import DetectionConfig, PreprocessingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.io.czi import CziSource
from apkit4d.pipeline.frame_stages import (
    coerce_blob_params,
    coerce_preproc_params,
    coerce_roi,
    crop_frame,
    detect_blobs_in_frame,
    preprocess_frame,
)

# Estimated memory peak per worker process on a typical 3D volume (in gigabytes)
RAM_PER_WORKER_GB: Final[float] = 1.2


def cap_workers(
    requested: int,
    per_worker_gb: float = RAM_PER_WORKER_GB,
    ram_fraction: float = 0.6,
) -> tuple[int, str]:
    """Limit worker processes to avoid exhausting system RAM.

    Each worker process holds the 3D volume and intermediate float32 arrays in memory.

    Args:
        requested: Number of worker processes requested by caller.
        per_worker_gb: Estimated RAM required per worker in gigabytes.
        ram_fraction: Maximum fraction of available RAM allowed for workers.

    Returns:
        Tuple of (capped_worker_count, reason_explanation).

    RefactorNote:
        Refactored from `batch.py`, function `cap_workers`.
    """
    try:
        avail_gb = psutil.virtual_memory().available / 1e9
    except Exception:
        return requested, ""

    cap = max(1, int(ram_fraction * avail_gb / per_worker_gb))
    if requested <= cap:
        return (
            requested,
            f"{avail_gb:.0f} GB free, ~{requested * per_worker_gb:.0f} GB estimated",
        )
    return cap, (
        f"reduced from {requested} to {cap}: {avail_gb:.0f} GB free, ~{per_worker_gb:.1f} GB per process"
    )


def detect_frame(
    src: CziSource,
    t: int,
    pp: PreprocessingConfig | dict[str, Any] | None = None,
    bp: DetectionConfig | dict[str, Any] | None = None,
    roi: RegionOfInterest | dict[str, Any] | Any | None = None,
    include_time: bool = False,
) -> pd.DataFrame:
    """Execute reading -> ROI crop -> preprocessing -> blob detection on a single frame.

    This function can be called directly by the GUI to inspect single-frame blob detections.

    Args:
        src: CziSource instance providing frame access.
        t: Zero-based frame timepoint index.
        pp: Preprocessing parameters (PreprocessingConfig or dict).
        bp: Blob detection parameters (DetectionConfig or dict).
        roi: Optional RegionOfInterest (world coordinates, micrometers) or dictionary
            specifying ROI bounds. None processes the whole volume.
        include_time: If True, inserts timestamp 't_s' at column index 1.

    Returns:
        DataFrame containing blob detections with DETECTION_COLUMNS.

    RefactorNote:
        Refactored from `batch.py`, function `detect_frame`.
    """
    volume = src.read(t)
    roi_obj = coerce_roi(roi)
    preproc_obj = coerce_preproc_params(pp)
    blob_obj = coerce_blob_params(bp)

    cropped = crop_frame(volume, frame=t, voxel_um=src.info.voxel, roi=roi_obj)
    preproc = preprocess_frame(cropped, preproc_obj)
    result = detect_blobs_in_frame(
        preproc,
        blob_obj,
        dt_s=src.info.dt_s,
        include_time=include_time,
        return_labels=False,
        require_normalized=False,
    )
    return result.detections


def _detect_frames_worker(
    czi_path: str | Path,
    channel: int,
    pp: PreprocessingConfig | dict[str, Any] | None = None,
    bp: DetectionConfig | dict[str, Any] | None = None,
    frames: list[int] | None = None,
    roi: RegionOfInterest | dict[str, Any] | Any | None = None,
    *,
    pp_dict: dict[str, Any] | None = None,
    bp_dict: dict[str, Any] | None = None,
) -> list[pd.DataFrame]:
    """Execute blob detection across a chunk of frames inside a worker process.

    Each worker instantiates its own CziSource since native file handles cannot be
    safely shared across processes. Parameter dataclasses (PreprocessingConfig,
    DetectionConfig, RegionOfInterest) are pickled directly across processes b
    ProcessPoolExecutor.

    Args:
        czi_path: Path to CZI microscopy acquisition file.
        channel: Channel index to process.
        pp: Preprocessing configuration (PreprocessingConfig or dict).
        bp: Blob detection configuration (DetectionConfig or dict).
        frames: List of frame indices to process.
        roi: Optional RegionOfInterest bounds specification or dict.
        pp_dict: Backward-compatible alias for pp.
        bp_dict: Backward-compatible alias for bp.

    Returns:
        List of detection DataFrames, one per frame.

    RefactorNote:
        Refactored from `batch.py`, function `_work`.
        Accepts direct dataclasses natively pickled by ProcessPoolExecutor while
        retaining dict/duck-typing compatibility.
    """
    if pp is None and pp_dict is not None:
        pp = pp_dict
    if bp is None and bp_dict is not None:
        bp = bp_dict

    preproc_params = coerce_preproc_params(pp)
    blob_params = coerce_blob_params(bp)
    roi_params = coerce_roi(roi)

    frame_list = frames if frames is not None else []
    src = CziSource(Path(czi_path), channel=channel)
    try:
        return [
            detect_frame(src, frame_idx, pp=preproc_params, bp=blob_params, roi=roi_params)
            for frame_idx in frame_list
        ]
    finally:
        src.close()
