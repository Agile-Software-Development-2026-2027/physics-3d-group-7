"""Pure per-frame stage functions shared by interactive GUI and bulk workers."""

import logging
from collections.abc import Mapping
from typing import Any, cast

import numpy as np

from apkit4d.core.image import Image
from apkit4d.core.roi import RegionOfInterest, VoxelSize3D
from apkit4d.detection.blob_detection import BlobParams, find_blobs
from apkit4d.detection.preprocessing import PreprocParams, preprocess
from apkit4d.pipeline.contracts import CroppedFrame, FrameDetectionResult, PreprocessedFrame

logger = logging.getLogger(__name__)


def coerce_roi(roi: RegionOfInterest | Mapping[str, Any] | Any | None) -> RegionOfInterest | None:
    """Convert a RegionOfInterest, dict, or duck-typed bounds object into RegionOfInterest."""
    if not roi:
        return None
    if isinstance(roi, RegionOfInterest):
        return roi
    if isinstance(roi, Mapping):
        return RegionOfInterest.from_dict(dict(roi))
    return RegionOfInterest(
        x_min=float(roi.x_min),
        x_max=float(roi.x_max),
        y_min=float(roi.y_min),
        y_max=float(roi.y_max),
        z_min=float(roi.z_min),
        z_max=float(roi.z_max),
    )


def coerce_preproc_params(params: PreprocParams | Mapping[str, Any] | None) -> PreprocParams:
    """Convert None or a mapping into a PreprocParams instance."""
    if params is None:
        return PreprocParams()
    if isinstance(params, PreprocParams):
        return params
    if isinstance(params, Mapping):
        # May want to add a check for keys that are not in PreprocParams to avoid silent errors
        return PreprocParams.from_dict(dict(params))


def coerce_blob_params(params: BlobParams | Mapping[str, Any] | None) -> BlobParams:
    """Convert None or a mapping into a BlobParams instance."""
    if params is None:
        return BlobParams()
    if isinstance(params, BlobParams):
        return params
    if isinstance(params, Mapping):
        # May want to add a check for keys that are not in BlobParams to avoid silent errors
        return BlobParams.from_dict(dict(params))


def crop_frame(
    raw_volume: Image[np.float32],
    frame: int,
    voxel_um: VoxelSize3D,
    roi: RegionOfInterest | None = None,
) -> CroppedFrame:
    """Stage 1: Slice raw 3D volume to ROI and compute physical and voxel offsets."""
    if roi is None:
        return CroppedFrame(
            frame=frame,
            raw_roi_volume=raw_volume,
            voxel_um=voxel_um,
            origin_xyz_um=(0.0, 0.0, 0.0),
            voxel_offset_zyx=(0, 0, 0),
        )

    shape = (int(raw_volume.shape[0]), int(raw_volume.shape[1]), int(raw_volume.shape[2]))
    slices, sub_origin_xyz = roi.to_voxel_slices(shape, voxel_um)
    offset_zyx = (
        int(slices[0].start or 0),
        int(slices[1].start or 0),
        int(slices[2].start or 0),
    )
    cropped_volume = cast(Image[np.float32], raw_volume[slices])
    return CroppedFrame(
        frame=frame,
        raw_roi_volume=cropped_volume,
        voxel_um=voxel_um,
        origin_xyz_um=sub_origin_xyz,
        voxel_offset_zyx=offset_zyx,
    )


def preprocess_frame(cropped: CroppedFrame, params: PreprocParams) -> PreprocessedFrame:
    """Stage 2: Run 3D denoising, background subtraction, normalization, gamma, and CLAHE."""
    processed = preprocess(cropped.raw_roi_volume, params, cropped.voxel_um)
    return PreprocessedFrame(cropped=cropped, image=processed, params=params)


def detect_blobs_in_frame(
    preproc: PreprocessedFrame,
    params: BlobParams,
    *,
    dt_s: float | None = None,
    include_time: bool = True,
    return_labels: bool = False,
    require_normalized: bool = False,
) -> FrameDetectionResult:
    """Stage 3: Detect 3D blobs on a PreprocessedFrame."""
    if require_normalized and not preproc.is_normalized:
        raise ValueError("Volume intensity normalization must be enabled before running blob detection.")

    if not preproc.is_normalized:
        logger.debug(
            "Running blob detection on frame %d without intensity normalization enabled.",
            preproc.cropped.frame,
        )

    df, labels, seeds = find_blobs(
        image=preproc.image,
        p=params,
        voxel_dim=preproc.cropped.voxel_um,
        intensity=preproc.cropped.raw_roi_volume,
        frame=preproc.cropped.frame,
        offset=preproc.cropped.voxel_offset_zyx,
        return_labels=return_labels,
    )

    if include_time:
        df = df.copy()
        timestamp = preproc.cropped.frame * dt_s if dt_s is not None else np.nan
        df.insert(1, "t_s", np.full(len(df), timestamp, dtype=np.float64))

    return FrameDetectionResult(
        frame=preproc.cropped.frame,
        detections=df,
        seeds_response=seeds,
        labels=labels,
    )
