"""Unit tests for DetectionSink implementations (memory, disk, and tee)."""

import json
from enum import Enum
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from apkit4d.io.table import read_table
from apkit4d.pipeline.contracts import SequenceDetectionResult
from apkit4d.pipeline.sinks import (
    DEFAULT_DETECTION_COLUMNS,
    InMemoryDetectionSink,
    StreamingDiskDetectionSink,
    TeeDetectionSink,
    json_serializable,
)


class _SampleEnum(Enum):
    ALPHA = "alpha"


def _frame_df(frame: int, coords: list[tuple[float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "frame": [frame] * len(coords),
            "t_s": [frame * 0.5] * len(coords),
            "z_um": [c[0] for c in coords],
            "y_um": [c[1] for c in coords],
            "x_um": [c[2] for c in coords],
        }
    )


def test_in_memory_sink_collects_and_sorts_frames() -> None:
    """InMemoryDetectionSink combines out-of-order frames sorted deterministically."""
    sink = InMemoryDetectionSink(num_frames=3)
    sink.on_frame_detections(2, _frame_df(2, [(3.0, 4.0, 5.0)]))
    sink.on_frame_detections(1, pd.DataFrame(columns=["frame", "t_s", "z_um", "y_um", "x_um"]))
    sink.on_frame_detections(0, _frame_df(0, [(1.0, 2.0, 3.0), (1.5, 2.5, 3.5)]))

    result = sink.finalize({"t0": 0, "t1": 2})

    assert isinstance(result, SequenceDetectionResult)
    assert result.table_path is None
    assert result.params_path is None
    assert result.num_blobs == 3
    assert result.num_frames == 3
    assert result.detections is not None
    assert result.detections["frame"].tolist() == [0, 0, 2]
    assert result.metadata["n_blobs"] == 3
    assert result.metadata["sorted_by_frame"] is True
    assert result.metadata["blobs_per_frame_mean"] == pytest.approx(1.0)


def test_in_memory_sink_empty_returns_schema_dataframe() -> None:
    """InMemoryDetectionSink emits an empty schema-preserving DataFrame when zero blobs match."""
    sink = InMemoryDetectionSink()
    sink.on_frame_detections(0, pd.DataFrame())
    sink.on_frame_detections(1, pd.DataFrame())

    result = sink.finalize({"t0": 0, "t1": 1})

    assert result.num_blobs == 0
    assert result.num_frames == 2
    assert result.detections is not None
    assert result.detections.empty
    assert list(result.detections.columns) == list(DEFAULT_DETECTION_COLUMNS)


def test_streaming_disk_sink_writes_table_and_params(tmp_path: Path) -> None:
    """StreamingDiskDetectionSink streams rows to disk and writes params JSON."""
    table_file = tmp_path / "blobs.csv"
    params_file = tmp_path / "nested" / "params.json"
    sink = StreamingDiskDetectionSink(table_file, params_file, num_frames=2)

    sink.on_frame_detections(0, _frame_df(0, [(1.0, 2.0, 3.0)]))
    sink.on_frame_detections(1, _frame_df(1, [(4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]))
    result = sink.finalize({"t0": 0, "t1": 1, "marker": _SampleEnum.ALPHA})

    assert result.detections is None
    assert result.table_path == table_file
    assert result.params_path == params_file
    assert result.num_blobs == 3
    assert result.num_frames == 2

    loaded = read_table(table_file)
    assert len(loaded) == 3
    assert loaded["frame"].tolist() == [0, 1, 1]

    meta = json.loads(params_file.read_text())
    assert meta["n_blobs"] == 3
    assert meta["marker"] == "alpha"
    assert meta["blobs_per_frame_mean"] == pytest.approx(1.5)


def test_tee_detection_sink_outputs_memory_and_disk(tmp_path: Path) -> None:
    """TeeDetectionSink populates both in-memory DataFrame and disk files."""
    table_file = tmp_path / "tee.csv"
    params_file = tmp_path / "tee_params.json"
    memory_sink = InMemoryDetectionSink()
    disk_sink = StreamingDiskDetectionSink(table_file, params_file)
    tee = TeeDetectionSink(memory_sink, disk_sink)

    assert len(tee.sinks) == 2

    tee.on_frame_detections(0, _frame_df(0, [(1.0, 2.0, 3.0)]))
    tee.on_frame_detections(1, _frame_df(1, [(4.0, 5.0, 6.0)]))
    result = tee.finalize({"t0": 0, "t1": 1})

    assert result.num_blobs == 2
    assert result.num_frames == 2
    assert result.detections is not None
    assert len(result.detections) == 2
    assert result.table_path == table_file
    assert result.params_path == params_file
    assert table_file.is_file()
    assert params_file.is_file()


def test_json_serializable_handles_custom_types() -> None:
    """Verify fallback JSON serializer conversions and unsupported error."""
    assert json_serializable(_SampleEnum.ALPHA) == "alpha"
    assert json_serializable(Path("a/b.czi")) == str(Path("a/b.czi"))
    assert json_serializable(np.int64(7)) == 7
    assert json_serializable(np.array([1, 2])) == [1, 2]
    with pytest.raises(TypeError):
        json_serializable(object())
