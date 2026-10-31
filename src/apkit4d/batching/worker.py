"""Worker-level frame detection, ROI extraction, and process resource management.

This module provides the core per-frame blob detection pipeline and worker task functions
executed across parallel processes.

RefactorNote:
    Modernized replacement for `detect_frame`, `_work`, and `cap_workers`
    from legacy `batch.py` (lines 37-75).
    Uses `RegionOfInterest` from `apkit4d.roi` for volume slicing and offset calculation.
    All single-letter variables replaced with clear (hpefully) names.
    And yeah apparently they tought about making some sort of worker system, pretty sus.
"""

from pathlib import Path
from typing import Any, Final

import numpy as np
import pandas as pd
import psutil

from apkit4d.blob_detection import BlobParams, find_blobs
from apkit4d.io.czi import CziSource
from apkit4d.preprocessing import PreprocParams, denoise
from apkit4d.roi import RegionOfInterest

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
    pp: PreprocParams | dict[str, Any] | None = None,
    bp: BlobParams | dict[str, Any] | None = None,
    roi: RegionOfInterest | dict[str, Any] | Any | None = None,
    include_time: bool = False,
) -> pd.DataFrame:
    """Execute reading -> ROI crop -> preprocessing -> blob detection on a single frame.

    This function can be called directly by the GUI to inspect single-frame blob detections.

    Args:
        src: CziSource instance providing frame access.
        t: Zero-based frame timepoint index.
        pp: Preprocessing parameters (PreprocParams or dict).
        bp: Blob detection parameters (BlobParams or dict).
        roi: Optional RegionOfInterest or dictionary specifying ROI bounds.
        include_time: If True, inserts timestamp 't_s' at column index 1.

    Returns:
        DataFrame containing blob detections with DETECTION_COLUMNS.

    RefactorNote:
        Refactored from `batch.py`, function `detect_frame`.
    """
    volume = src.read(t)

    roi_obj: RegionOfInterest
    if roi is None:
        roi_obj = RegionOfInterest()
    elif isinstance(roi, RegionOfInterest):
        roi_obj = roi
    elif isinstance(roi, dict):
        roi_obj = RegionOfInterest.from_dict(roi)
    else:
        roi_obj = RegionOfInterest(
            z0=getattr(roi, "z0", None),
            z1=getattr(roi, "z1", None),
            y0=getattr(roi, "y0", None),
            y1=getattr(roi, "y1", None),
            x0=getattr(roi, "x0", None),
            x1=getattr(roi, "x1", None),
        )

    vol_shape = (volume.shape[0], volume.shape[1], volume.shape[2])
    slices = roi_obj.slices(vol_shape)
    offset = roi_obj.offset(vol_shape)
    vol_roi = volume[slices]

    preproc_obj: PreprocParams
    if pp is None:
        preproc_obj = PreprocParams()
    elif isinstance(pp, dict):
        preproc_obj = PreprocParams.from_dict(pp)
    else:
        preproc_obj = pp

    preprocessed_img = denoise(vol_roi, preproc_obj, src.info.voxel)

    blob_obj: BlobParams
    if bp is None:
        blob_obj = BlobParams()
    elif isinstance(bp, dict):
        blob_obj = BlobParams.from_dict(bp)
    else:
        blob_obj = bp

    detections, _, _ = find_blobs(
        image=preprocessed_img,
        p=blob_obj,
        voxel_dim=src.info.voxel,
        intensity=vol_roi,
        frame=t,
        offset=offset,
    )

    if include_time and len(detections) > 0:
        detections = detections.copy()
        time_seconds = t * src.info.dt_s if src.info.dt_s is not None else np.nan
        detections.insert(1, "t_s", time_seconds)

    return detections


def _detect_frames_worker(
    czi_path: str | Path,
    channel: int,
    pp_dict: dict[str, Any] | None,
    bp_dict: dict[str, Any] | None,
    frames: list[int],
    roi: RegionOfInterest | dict[str, Any] | Any | None = None,
) -> list[pd.DataFrame]:
    """Execute blob detection across a chunk of frames inside a worker process.

    Each worker instantiates its own CziSource since native file handles cannot be
    safely shared across processes.

    Args:
        czi_path: Path to CZI microscopy acquisition file.
        channel: Channel index to process.
        pp_dict: Serialized preprocessing configuration dict.
        bp_dict: Serialized blob detection configuration dict.
        frames: List of frame indices to process.
        roi: Optional RegionOfInterest bounds specification.

    Returns:
        List of detection DataFrames, one per frame.

    RefactorNote:
        Refactored from `batch.py`, function `_work`.
        This function existfor mostly because we're porting nearly 1-1 legacy code,the worker system may
        change in the future.
    """
    src = CziSource(Path(czi_path), channel=channel)
    try:
        preproc_params = PreprocParams.from_dict(pp_dict) if pp_dict is not None else PreprocParams()
        blob_params = BlobParams.from_dict(bp_dict) if bp_dict is not None else BlobParams()
        return [
            detect_frame(src, frame_idx, pp=preproc_params, bp=blob_params, roi=roi) for frame_idx in frames
        ]
    finally:
        src.close()
