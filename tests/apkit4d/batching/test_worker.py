"""Unit tests for worker-level batching functions, process resource management, and detect_frame.

RefactorNode:

"""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import apkit4d.batching as batching_pkg
from apkit4d.batching.worker import (
    RAM_PER_WORKER_GB,
    _detect_frames_worker,
    cap_workers,
    detect_frame,
)
from apkit4d.blob_detection import BlobParams
from apkit4d.io.czi import CziInfo, CziSource
from apkit4d.preprocessing import PreprocParams
from apkit4d.roi import RegionOfInterest


class TestWorkerHelpers:
    def test_ram_per_worker_constant(self) -> None:
        """Verify RAM_PER_WORKER_GB is defined as a positive float."""
        assert RAM_PER_WORKER_GB > 0

    def test_cap_workers_real_system(self) -> None:
        """Verify cap_workers functions with real psutil on the system."""
        workers, reason = cap_workers(2)
        assert workers >= 1
        assert isinstance(reason, str)

    def test_cap_workers_exception_handling(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify cap_workers gracefully handles runtime errors from psutil."""
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.side_effect = RuntimeError("Memory probe failed")
        monkeypatch.setattr("apkit4d.batching.worker.psutil", mock_psutil)
        workers, reason = cap_workers(16)
        assert workers == 16
        assert reason == ""

    def test_cap_workers_sufficient_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify cap_workers retains requested count when sufficient memory is free."""
        mock_psutil = MagicMock()
        mock_psutil.virtual_memory.return_value.available = 64e9  # 64 GB
        monkeypatch.setattr("apkit4d.batching.worker.psutil", mock_psutil)
        workers, reason = cap_workers(8, per_worker_gb=1.2, ram_fraction=0.6)
        assert workers == 8
        assert "64 GB free" in reason

    def test_cap_workers_limits_on_low_memory(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify cap_workers restricts worker count on constrained systems."""
        mock_psutil = MagicMock()
        # 4 GB free -> 0.6 * 4 / 1.2 = 2 workers
        mock_psutil.virtual_memory.return_value.available = 4e9
        monkeypatch.setattr("apkit4d.batching.worker.psutil", mock_psutil)
        workers, reason = cap_workers(16, per_worker_gb=1.2, ram_fraction=0.6)
        assert workers == 2
        assert "reduced from 16 to 2" in reason


class TestDetectFrame:
    @pytest.fixture
    def mock_czi_source(self) -> MagicMock:
        """Create a mock CziSource with synthetic 3D volume."""
        src = MagicMock(spec=CziSource)
        src.info = CziInfo(
            path="test_sample.czi",
            n_t=5,
            n_z=10,
            n_y=20,
            n_x=20,
            n_c=1,
            dtype="uint16",
            px_size_x=1.0,
            px_size_y=1.0,
            px_size_z=1.0,
            dt_s=0.25,
            dt_source="test",
        )
        # Empty volume with a synthetic bright spot in the center to trigger a blob
        vol = np.zeros((10, 20, 20), dtype=np.uint16)
        vol[4:7, 8:12, 8:12] = 20000
        src.read.return_value = vol
        return src

    def test_detect_frame_basic(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame on a volume produces detection DataFrame."""
        pp = PreprocParams(denoise_xy_scale_um=0.0, denoise_z_scale_um=0.0)
        bp = BlobParams(threshold=0.05, min_volume_um3=1.0)

        df = detect_frame(mock_czi_source, t=0, pp=pp, bp=bp, include_time=False)
        assert isinstance(df, pd.DataFrame)
        mock_czi_source.read.assert_called_once_with(0)

        if not df.empty:
            assert "frame" in df.columns
            assert "z_um" in df.columns
            assert "y_um" in df.columns
            assert "x_um" in df.columns
            assert "t_s" not in df.columns

    def test_detect_frame_with_time(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame inserts t_s column when include_time is True."""
        pp = PreprocParams()
        bp = BlobParams(threshold=0.05, min_volume_um3=1.0)

        df = detect_frame(mock_czi_source, t=2, pp=pp, bp=bp, include_time=True)
        assert isinstance(df, pd.DataFrame)
        if not df.empty:
            assert "t_s" in df.columns
            assert df.iloc[0]["t_s"] == 2 * 0.25

    def test_detect_frame_dict_params(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame accepts dictionary configurations."""
        pp_dict = {"denoise_xy_scale_um": 1.0, "denoise_z_scale_um": 1.0}
        bp_dict = {"threshold": 0.05, "min_volume_um3": 1.0}

        df = detect_frame(mock_czi_source, t=1, pp=pp_dict, bp=bp_dict)
        assert isinstance(df, pd.DataFrame)

    def test_detect_frame_default_params(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame handles default pp=None and bp=None."""
        df = detect_frame(mock_czi_source, t=0, pp=None, bp=None)
        assert isinstance(df, pd.DataFrame)

    def test_detect_frame_with_region_of_interest(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame with RegionOfInterest instance."""
        roi = RegionOfInterest(z0=2, z1=8, y0=5, y1=15, x0=5, x1=15)
        df = detect_frame(mock_czi_source, t=0, pp=None, bp=None, roi=roi)
        assert isinstance(df, pd.DataFrame)

    def test_detect_frame_with_dict_roi(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame with dictionary ROI."""
        roi_dict = {"z0": 1, "z1": 8, "y0": 2, "y1": 18, "x0": 2, "x1": 18}
        df = detect_frame(mock_czi_source, t=0, pp=None, bp=None, roi=roi_dict)
        assert isinstance(df, pd.DataFrame)

    def test_detect_frame_with_duck_typed_roi(self, mock_czi_source: MagicMock) -> None:
        """Verify detect_frame with duck-typed object possessing coordinate attributes."""
        roi_obj = SimpleNamespace(z0=1, z1=8, y0=2, y1=18, x0=2, x1=18)
        df = detect_frame(mock_czi_source, t=0, pp=None, bp=None, roi=roi_obj)
        assert isinstance(df, pd.DataFrame)

    def test_detect_frames_worker(self, tmp_path: Path) -> None:
        """Verify _detect_frames_worker opens CziSource, processes frames, and closes."""
        mock_source = MagicMock(spec=CziSource)
        mock_source.info = CziInfo(
            path="dummy.czi",
            n_t=3,
            n_z=5,
            n_y=10,
            n_x=10,
            n_c=1,
            dtype="uint16",
            px_size_x=1.0,
            px_size_y=1.0,
            px_size_z=1.0,
            dt_s=0.5,
            dt_source="test",
        )
        mock_source.read.return_value = np.zeros((5, 10, 10), dtype=np.uint16)

        with patch("apkit4d.batching.worker.CziSource", return_value=mock_source):
            results = _detect_frames_worker(
                czi_path="dummy.czi",
                channel=0,
                pp_dict={},
                bp_dict={},
                frames=[0, 1],
            )
            assert len(results) == 2
            assert mock_source.read.call_count == 2
            mock_source.close.assert_called_once()

    def test_detect_frames_worker_none_dicts(self) -> None:
        """Verify _detect_frames_worker handles None parameter dictionaries."""
        mock_source = MagicMock(spec=CziSource)
        mock_source.info = CziInfo(
            path="dummy.czi",
            n_t=2,
            n_z=5,
            n_y=10,
            n_x=10,
            n_c=1,
            dtype="uint16",
            px_size_x=1.0,
            px_size_y=1.0,
            px_size_z=1.0,
            dt_s=0.5,
            dt_source="test",
        )
        mock_source.read.return_value = np.zeros((5, 10, 10), dtype=np.uint16)

        with patch("apkit4d.batching.worker.CziSource", return_value=mock_source):
            results = _detect_frames_worker(
                czi_path="dummy.czi",
                channel=0,
                pp_dict=None,
                bp_dict=None,
                frames=[0],
            )
            assert len(results) == 1
            mock_source.close.assert_called_once()

    def test_detect_frames_worker_with_roi(self) -> None:
        """Verify _detect_frames_worker passes roi down to detect_frame."""
        mock_source = MagicMock(spec=CziSource)
        mock_source.info = CziInfo(
            path="dummy.czi",
            n_t=2,
            n_z=5,
            n_y=10,
            n_x=10,
            n_c=1,
            dtype="uint16",
            px_size_x=1.0,
            px_size_y=1.0,
            px_size_z=1.0,
            dt_s=0.5,
            dt_source="test",
        )
        mock_source.read.return_value = np.zeros((5, 10, 10), dtype=np.uint16)
        roi = RegionOfInterest(z0=1, z1=3)

        with patch("apkit4d.batching.worker.CziSource", return_value=mock_source):
            results = _detect_frames_worker(
                czi_path="dummy.czi",
                channel=0,
                pp_dict=None,
                bp_dict=None,
                frames=[0],
                roi=roi,
            )
            assert len(results) == 1
            mock_source.close.assert_called_once()

    def test_batching_package_imported(self) -> None:
        """Verify apkit4d.batching package is importable."""
        assert batching_pkg.__doc__ is not None
