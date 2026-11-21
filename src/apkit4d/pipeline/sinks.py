"""Detection sink implementations for in-memory and streaming disk workflows.

What are sinkis: https://en.wikipedia.org/wiki/Sink_(computing)
"""

import json
import logging
from collections.abc import Sequence
from enum import Enum
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from apkit4d.detection.blob_detection import DETECTION_COLUMNS
from apkit4d.io.table import TableWriter
from apkit4d.pipeline.contracts import DetectionSink, SequenceDetectionResult

logger = logging.getLogger(__name__)

DEFAULT_DETECTION_COLUMNS: tuple[str, ...] = ("frame", "t_s", *DETECTION_COLUMNS[1:])


def json_serializable(obj: Any) -> Any:
    """Fallback ``default=`` serializer for ``json.dumps`` on metadata dictionaries.

    Core pipeline config dataclasses already serialize natively (primitives and
    ``StrEnum``), so this acts as a defensive coercion hook when caller-supplied
    metadata contains non-``StrEnum`` enums, ``pathlib.Path`` instances, or NumPy
    scalars/arrays which, as you can imagine, are not JSON serializable by default.
    """
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (np.integer, np.floating)):
        return obj.item()
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError(f"Object of type {obj.__class__.__name__} is not JSON serializable")


def _resolve_num_frames(explicit_frames: int | None, metadata: dict[str, Any], seen_frames: int) -> int:
    """Determine processed frame count from explicit value, metadata bounds, or seen frames."""
    if explicit_frames is not None:
        return explicit_frames
    t0 = metadata.get("t0")
    t1 = metadata.get("t1")
    if isinstance(t0, int) and isinstance(t1, int):
        return max(0, t1 - t0 + 1)
    return seen_frames


class InMemoryDetectionSink:
    """Collect detected blobs in RAM and emit a concatenated DataFrame."""

    def __init__(
        self,
        *,
        num_frames: int | None = None,
        columns: Sequence[str] | None = None,
    ) -> None:
        """Initialize an in-memory detection sink.

        Args:
            num_frames: Optional explicit frame count for the finalized result.
            columns: Column schema used when zero detections are collected.
        """
        self._num_frames = num_frames
        self._empty_columns = list(columns) if columns is not None else list(DEFAULT_DETECTION_COLUMNS)
        self._chunks: list[pd.DataFrame] = []
        self._seen_frames: set[int] = set()

    def on_frame_detections(self, frame: int, df: pd.DataFrame) -> None:
        """Store detections for a single frame in memory."""
        self._seen_frames.add(frame)
        if df is not None and not df.empty:
            self._chunks.append(df.copy())

    def finalize(self, metadata: dict[str, Any]) -> SequenceDetectionResult:
        """Combine buffered frame detections and build SequenceDetectionResult."""
        if self._chunks:
            combined = pd.concat(self._chunks, ignore_index=True)
            if "frame" in combined.columns:
                combined = combined.sort_values("frame", kind="mergesort", ignore_index=True)
        else:
            combined = pd.DataFrame(columns=self._empty_columns)

        num_frames = _resolve_num_frames(self._num_frames, metadata, len(self._seen_frames))
        num_blobs = int(len(combined))

        final_meta = dict(metadata)
        final_meta["n_blobs"] = num_blobs
        final_meta["sorted_by_frame"] = True
        final_meta["ordinato_per_frame"] = True
        final_meta["blobs_per_frame_mean"] = float(num_blobs / max(1, num_frames))

        logger.debug("Finalized in-memory detection sink: %d blobs across %d frames", num_blobs, num_frames)
        return SequenceDetectionResult(
            detections=combined,
            table_path=None,
            params_path=None,
            num_blobs=num_blobs,
            num_frames=num_frames,
            metadata=final_meta,
        )


class StreamingDiskDetectionSink:
    """Stream detected blobs incrementally to Parquet/CSV and write params JSON."""

    def __init__(
        self,
        table_path: str | Path,
        params_path: str | Path,
        *,
        num_frames: int | None = None,
    ) -> None:
        """Initialize streaming disk sink backed by TableWriter.

        Args:
            table_path: Destination detection table file (.parquet or .csv).
            params_path: Destination metadata JSON file path.
            num_frames: Optional explicit frame count for the finalized result.
        """
        self._table_path = Path(table_path)
        self._params_path = Path(params_path)
        self._num_frames = num_frames
        self._writer = TableWriter(self._table_path)
        self._seen_frames: set[int] = set()
        self._closed = False

    def on_frame_detections(self, frame: int, df: pd.DataFrame) -> None:
        """Append non-empty frame detections to the underlying TableWriter."""
        self._seen_frames.add(frame)
        if df is not None and not df.empty:
            self._writer.append(df)

    def close(self) -> None:
        """Close the underlying TableWriter if still open."""
        if not self._closed:
            self._writer.close()
            self._closed = True

    def finalize(self, metadata: dict[str, Any]) -> SequenceDetectionResult:
        """Flush and close the table writer, persist metadata JSON, and return result."""
        self.close()
        num_frames = _resolve_num_frames(self._num_frames, metadata, len(self._seen_frames))
        total_blobs = int(self._writer.n_rows)

        final_meta = dict(metadata)
        final_meta["n_blobs"] = total_blobs
        final_meta["blobs_per_frame_mean"] = float(total_blobs / max(1, num_frames))

        self._params_path.parent.mkdir(parents=True, exist_ok=True)
        self._params_path.write_text(json.dumps(final_meta, indent=2, default=json_serializable))

        logger.debug(
            "Finalized streaming disk sink: %d blobs across %d frames -> %s",
            total_blobs,
            num_frames,
            self._table_path,
        )
        return SequenceDetectionResult(
            detections=None,
            table_path=self._table_path,
            params_path=self._params_path,
            num_blobs=total_blobs,
            num_frames=num_frames,
            metadata=final_meta,
        )


class TeeDetectionSink:
    """Fan frame detections out to both an in-memory sink and a disk sink."""

    def __init__(
        self,
        memory_sink: InMemoryDetectionSink,
        disk_sink: StreamingDiskDetectionSink,
    ) -> None:
        """Initialize a tee sink forwarding every frame to RAM and disk sinks."""
        self._memory_sink = memory_sink
        self._disk_sink = disk_sink

    @property
    def sinks(self) -> tuple[DetectionSink, DetectionSink]:
        """Return child sinks for inspection or testing."""
        return (self._memory_sink, self._disk_sink)

    def on_frame_detections(self, frame: int, df: pd.DataFrame) -> None:
        """Forward frame detections to both memory and disk sinks."""
        self._memory_sink.on_frame_detections(frame, df)
        self._disk_sink.on_frame_detections(frame, df)

    def close(self) -> None:
        """Close the child disk sink if needed."""
        self._disk_sink.close()

    def finalize(self, metadata: dict[str, Any]) -> SequenceDetectionResult:
        """Finalize both child sinks and merge outputs into SequenceDetectionResult."""
        disk_result = self._disk_sink.finalize(metadata)
        memory_result = self._memory_sink.finalize(disk_result.metadata)
        return SequenceDetectionResult(
            detections=memory_result.detections,
            table_path=disk_result.table_path,
            params_path=disk_result.params_path,
            num_blobs=memory_result.num_blobs,
            num_frames=memory_result.num_frames,
            metadata=disk_result.metadata,
        )
