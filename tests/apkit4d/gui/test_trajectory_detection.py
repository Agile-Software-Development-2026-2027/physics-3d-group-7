"""Tests for trajectory detection data preparation."""

from pathlib import Path

import pandas as pd
import pytest

from apkit4d.batching.processor import BatchProcessor, BatchResult
from apkit4d.blob_detection import BlobParams
from apkit4d.gui.controllers.trajectory_detection import detect_sequence
from apkit4d.preprocessing import PreprocParams


def test_detect_sequence_returns_detections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Read detected blobs and timing information."""
    czi_path = tmp_path / "sample.czi"

    expected = pd.DataFrame(
        {
            "frame": [0, 1],
            "z_um": [1.0, 1.0],
            "y_um": [2.0, 2.0],
            "x_um": [3.0, 4.0],
        }
    )

    def fake_process(self, czi, *, out_dir, roi):
        assert czi == czi_path
        assert self.config.workers == 1
        assert roi is None

        table_path = Path(out_dir) / "blobs.csv"
        expected.to_csv(table_path, index=False)

        return BatchResult(
            table_path=table_path,
            params_path=Path(out_dir) / "params.json",
            num_blobs=2,
            num_frames=2,
            metadata={"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(BatchProcessor, "process", fake_process)

    result = detect_sequence(
        czi_path,
        PreprocParams(),
        BlobParams(),
    )

    pd.testing.assert_frame_equal(result.detections, expected)
    assert result.dt_s == 0.5
    assert result.metadata["info"]["dt_s"] == 0.5


def test_detect_sequence_handles_empty_detections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Return an empty table when no blobs are found."""

    def fake_process(self, czi, *, out_dir, roi):
        return BatchResult(
            table_path=Path(out_dir) / "missing.csv",
            params_path=Path(out_dir) / "params.json",
            num_blobs=0,
            num_frames=3,
            metadata={"info": {"dt_s": None}},
        )

    monkeypatch.setattr(BatchProcessor, "process", fake_process)

    result = detect_sequence(
        tmp_path / "sample.czi",
        PreprocParams(),
        BlobParams(),
    )

    assert result.detections.empty
    assert list(result.detections.columns) == ["frame", "z_um", "y_um", "x_um"]
    assert result.dt_s is None


def test_detect_sequence_reuses_open_czi_source(monkeypatch, tmp_path) -> None:
    """Processing an open source must not reopen the CZI."""
    from unittest.mock import MagicMock

    from apkit4d.io.czi import CziSource

    source = MagicMock(spec=CziSource)
    source.path = tmp_path / "sample.czi"
    source.channel = 1

    expected = pd.DataFrame(
        {
            "frame": [0],
            "z_um": [0.0],
            "y_um": [0.0],
            "x_um": [0.0],
        }
    )

    def fake_process(self, czi, *, out_dir, roi):
        assert czi is source
        assert roi is None

        path = Path(out_dir) / "blobs.csv"
        expected.to_csv(path, index=False)

        return BatchResult(
            table_path=path,
            params_path=Path(out_dir) / "params.json",
            num_blobs=1,
            num_frames=1,
            metadata={"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(BatchProcessor, "process", fake_process)

    result = detect_sequence(
        source,
        PreprocParams(),
        BlobParams(),
    )

    pd.testing.assert_frame_equal(result.detections, expected)
