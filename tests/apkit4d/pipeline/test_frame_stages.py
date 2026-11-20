"""Unit tests for unified per-frame pipeline contracts and pure stage functions."""

from types import SimpleNamespace

import numpy as np
import pytest

from apkit4d.blob_detection import BlobParams
from apkit4d.pipeline.contracts import (
    CroppedFrame,
    FrameDetectionResult,
    PreprocessedFrame,
)
from apkit4d.pipeline.frame_stages import (
    coerce_blob_params,
    coerce_preproc_params,
    coerce_roi,
    crop_frame,
    detect_blobs_in_frame,
    preprocess_frame,
)
from apkit4d.preprocessing import PreprocParams
from apkit4d.roi import RegionOfInterest


class TestCoercionHelpers:
    def test_coerce_roi_variants(self) -> None:
        assert coerce_roi(None) is None
        assert coerce_roi({}) is None

        roi = RegionOfInterest(x_min=1.0, x_max=5.0, y_min=2.0, y_max=6.0, z_min=0.0, z_max=4.0)
        assert coerce_roi(roi) is roi

        from_dict = coerce_roi(roi.to_dict())
        assert from_dict == roi

        duck = SimpleNamespace(x_min=1, x_max=5, y_min=2, y_max=6, z_min=0, z_max=4)
        assert coerce_roi(duck) == roi

    def test_coerce_preproc_params_variants(self) -> None:
        assert coerce_preproc_params(None) == PreprocParams()
        custom = PreprocParams(normalization_enabled=True, lowest_intensity=10.0)
        assert coerce_preproc_params(custom) is custom
        assert coerce_preproc_params({"normalization_enabled": True, "lowest_intensity": 10.0}) == custom
        with pytest.raises(TypeError, match="Unsupported preprocessing parameters type"):
            coerce_preproc_params("invalid")

    def test_coerce_blob_params_variants(self) -> None:
        assert coerce_blob_params(None) == BlobParams()
        custom = BlobParams(threshold=0.25)
        assert coerce_blob_params(custom) is custom
        assert coerce_blob_params({"threshold": 0.25}) == custom
        with pytest.raises(TypeError, match="Unsupported blob parameters type"):
            coerce_blob_params(123)


class TestFrameStages:
    def test_crop_frame_full_volume(self) -> None:
        vol = np.arange(8 * 10 * 12, dtype=np.uint16).reshape(8, 10, 12)
        cropped = crop_frame(vol, frame=3, voxel_um=(2.0, 1.0, 1.0), roi=None)

        assert isinstance(cropped, CroppedFrame)
        assert cropped.frame == 3
        assert cropped.raw_roi_volume is vol
        assert cropped.voxel_um == (2.0, 1.0, 1.0)
        assert cropped.origin_xyz_um == (0.0, 0.0, 0.0)
        assert cropped.voxel_offset_zyx == (0, 0, 0)

    def test_crop_frame_with_roi_preserves_slice_and_offsets(self) -> None:
        vol = np.arange(8 * 16 * 16, dtype=np.uint16).reshape(8, 16, 16)
        roi = RegionOfInterest(x_min=4.0, x_max=10.0, y_min=2.0, y_max=8.0, z_min=2.0, z_max=6.0)
        voxel = (2.0, 1.0, 1.0)

        cropped = crop_frame(vol, frame=1, voxel_um=voxel, roi=roi)

        oz, oy, ox = cropped.voxel_offset_zyx
        dz, dy, dx = cropped.raw_roi_volume.shape
        assert (oz, oy, ox) == (1, 2, 4)
        assert cropped.origin_xyz_um == (4.0, 2.0, 2.0)
        assert np.array_equal(vol[oz : oz + dz, oy : oy + dy, ox : ox + dx], cropped.raw_roi_volume)

    def test_preprocess_and_detect_blobs_in_frame(self) -> None:
        vol = np.zeros((10, 20, 20), dtype=np.uint16)
        vol[4:7, 8:12, 8:12] = 20000
        roi = RegionOfInterest(x_min=4.0, x_max=16.0, y_min=4.0, y_max=16.0, z_min=2.0, z_max=8.0)

        cropped = crop_frame(vol, frame=2, voxel_um=(1.0, 1.0, 1.0), roi=roi)
        pp_norm = PreprocParams(normalization_enabled=True, lowest_intensity=0.0, highest_intensity=20000.0)
        preproc = preprocess_frame(cropped, pp_norm)

        assert isinstance(preproc, PreprocessedFrame)
        assert preproc.is_normalized is True
        assert preproc.image.dtype == np.float32

        bp = BlobParams(threshold=0.05, min_volume_um3=1.0, diameter_xy_um=4.0, diameter_z_um=4.0)
        result = detect_blobs_in_frame(
            preproc,
            bp,
            dt_s=0.25,
            include_time=True,
            return_labels=True,
            require_normalized=True,
        )

        assert isinstance(result, FrameDetectionResult)
        assert result.frame == 2
        assert result.labels is not None
        assert not result.detections.empty
        assert list(result.detections.columns[:2]) == ["frame", "t_s"]
        assert result.detections.iloc[0]["frame"] == 2
        assert result.detections.iloc[0]["t_s"] == pytest.approx(0.5)
        # Coordinates must be shifted back into full-volume world coordinates
        assert result.detections.iloc[0]["x_um"] >= 4.0
        assert result.detections.iloc[0]["y_um"] >= 4.0
        assert result.detections.iloc[0]["z_um"] >= 2.0

    def test_detect_blobs_in_frame_require_normalized_raises(self) -> None:
        vol = np.zeros((6, 8, 8), dtype=np.uint16)
        cropped = crop_frame(vol, frame=0, voxel_um=(1.0, 1.0, 1.0))
        preproc = preprocess_frame(cropped, PreprocParams(normalization_enabled=False))

        assert preproc.is_normalized is False
        with pytest.raises(ValueError, match="normalization must be enabled"):
            detect_blobs_in_frame(preproc, BlobParams(), require_normalized=True)

    def test_detect_blobs_in_frame_without_time_or_dt(self) -> None:
        vol = np.zeros((6, 8, 8), dtype=np.uint16)
        cropped = crop_frame(vol, frame=1, voxel_um=(1.0, 1.0, 1.0))
        preproc = preprocess_frame(cropped, PreprocParams(normalization_enabled=True))

        res_no_time = detect_blobs_in_frame(preproc, BlobParams(), include_time=False)
        assert "t_s" not in res_no_time.detections.columns

        res_nan_time = detect_blobs_in_frame(preproc, BlobParams(), dt_s=None, include_time=True)
        assert "t_s" in res_nan_time.detections.columns
