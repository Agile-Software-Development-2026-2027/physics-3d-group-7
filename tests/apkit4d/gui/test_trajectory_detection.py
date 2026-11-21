"""Tests for trajectory detection data preparation."""

from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from apkit4d.batching.processor import BatchProcessor
from apkit4d.detection.blob_detection import BlobParams
from apkit4d.detection.preprocessing import PreprocParams
from apkit4d.gui.controllers.trajectory_detection import detect_sequence
from apkit4d.io.czi import CziInfo, CziSource
from apkit4d.pipeline.contracts import SequenceDetectionResult
from apkit4d.pipeline.sinks import InMemoryDetectionSink


def test_detect_sequence_returns_detections(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Use InMemoryDetectionSink without writing temporary files to disk."""
    czi_path = tmp_path / "sample.czi"

    expected = pd.DataFrame(
        {
            "frame": [0, 1],
            "z_um": [1.0, 1.0],
            "y_um": [2.0, 2.0],
            "x_um": [3.0, 4.0],
        }
    )

    def fake_process_sequence(self, czi, *, roi, sink):
        assert czi == czi_path
        assert self.config.workers == 1
        assert roi is None
        assert isinstance(sink, InMemoryDetectionSink)

        return SequenceDetectionResult(
            detections=expected,
            table_path=None,
            params_path=None,
            num_blobs=2,
            num_frames=2,
            metadata={"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(BatchProcessor, "process_sequence", fake_process_sequence)

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

    def fake_process_sequence(self, czi, *, roi, sink):
        return SequenceDetectionResult(
            detections=None,
            table_path=None,
            params_path=None,
            num_blobs=0,
            num_frames=3,
            metadata={"info": {"dt_s": None}},
        )

    monkeypatch.setattr(BatchProcessor, "process_sequence", fake_process_sequence)

    result = detect_sequence(
        tmp_path / "sample.czi",
        PreprocParams(),
        BlobParams(),
    )

    assert result.detections.empty
    assert list(result.detections.columns) == ["frame", "z_um", "y_um", "x_um"]
    assert result.dt_s is None


def test_detect_sequence_reuses_open_czi_source_without_disk_io(tmp_path: Path) -> None:
    """Execute detect_sequence end-to-end in RAM with an open CziSource and zero disk writes."""
    source = MagicMock(spec=CziSource)
    source.path = tmp_path / "nonexistent.czi"
    source.channel = 0
    source.info = CziInfo(
        path=str(source.path),
        n_t=2,
        n_z=10,
        n_y=20,
        n_x=20,
        n_c=1,
        dtype="uint16",
        px_size_x=1.0,
        px_size_z=1.0,
        px_size_y=1.0,
        dt_s=0.5,
        dt_source="test",
    )
    vol = np.zeros((10, 20, 20), dtype=np.uint16)
    vol[3:7, 8:13, 8:13] = 25000
    source.read.return_value = vol

    result = detect_sequence(
        source,
        PreprocParams(),
        BlobParams(threshold=0.05, min_volume_um3=1.0),
    )

    assert list(tmp_path.iterdir()) == []
    assert not result.detections.empty
    assert result.dt_s == 0.5
    source.close.assert_not_called()
