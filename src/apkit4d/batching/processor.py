"""Batch detection coordinator and execution engine.

Coordinates parallel multi-frame volume reading, preprocessing, blob detection,
streaming table persistence, and metadata recording.

RefactorNote:
    Modernized replacement for `run` and `main` entry points from legacy `batch.py` (lines 76-143).
    Follows the design established by `ParticleLinker` in `tracking/linker.py`,
    including frozen result dataclasses, configurable execution parameters, and English metadata.
"""

import logging
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from apkit4d.batching.worker import (
    _detect_frames_worker,
    cap_workers,
    detect_frame,
)
from apkit4d.core.models import BatchConfig, DetectionConfig, PreprocessingConfig
from apkit4d.io.czi import CziSource
from apkit4d.io.table import table_path
from apkit4d.pipeline.contracts import DetectionSink, SequenceDetectionResult
from apkit4d.pipeline.sinks import InMemoryDetectionSink, StreamingDiskDetectionSink

logger = logging.getLogger(__name__)


def _prepare_frame_detections(detections: pd.DataFrame, frame_idx: int, dt_s: float | None) -> pd.DataFrame:
    """Attach the acquisition timestamp column to non-empty per-frame detections."""
    if len(detections) == 0:
        return detections
    prepared = detections.copy()
    if "t_s" not in prepared.columns:
        timestamp = frame_idx * dt_s if dt_s is not None else np.nan
        prepared.insert(1, "t_s", timestamp)
    return prepared


def stem_of(czi_path: str | Path) -> str:
    """Extract filesystem stem with spaces replaced by underscores.

    Args:
        czi_path: Path to acquisition file.

    Returns:
        Sanitized stem string.

    RefactorNote:
        Modernized equivalent of `stem_of` from legacy `params.py` (line 20).
    """
    return Path(czi_path).stem.replace(" ", "_")


@dataclass(frozen=True)
class BatchResult:
    """Result returned by BatchProcessor execution.

    Attributes:
        table_path: Path to the generated detection table file (parquet or csv).
        params_path: Path to the metadata configuration JSON file.
        num_blobs: Total number of blobs detected across all processed frames.
        num_frames: Total number of frames successfully processed.
        metadata: Comprehensive execution and configuration metadata dictionary.
    """

    table_path: Path
    params_path: Path
    num_blobs: int
    num_frames: int
    metadata: dict[str, Any]


class BatchProcessor:
    """Coordinator for parallel batch blob detection across CZI acquisition frames.

    RefactorNote:
        Modernized equivalent of `run` from legacy `batch.py` (lines 76-143).
        Designed to match the architectural patterns of ParticleLinker in tracking.
    """

    def __init__(
        self,
        config: BatchConfig | None = None,
        preproc_params: PreprocessingConfig | None = None,
        blob_params: DetectionConfig | None = None,
    ) -> None:
        """Initialize the batch processor with configuration parameters.

        Args:
            config: Batch processing configuration. If None, default settings are used.
            preproc_params: Preprocessing parameters. If None, defaults are used.
            blob_params: Blob detection parameters. If None, defaults are used.
        """
        self.config = config or BatchConfig()
        self.preproc_params = preproc_params or PreprocessingConfig()
        self.blob_params = blob_params or DetectionConfig()

    def _resolve_source(
        self,
        czi: str | Path | CziSource,
        channel: int,
    ) -> tuple[CziSource, Path, int, bool]:
        """Resolve an input path or open CziSource into (source, file_path, channel, should_close)."""
        if isinstance(czi, (str, Path)):
            file_path = Path(czi)
            return CziSource(file_path, channel=channel), file_path, channel, True
        return czi, Path(czi.path), czi.channel, False

    def process_sequence(
        self,
        czi: str | Path | CziSource,
        channel: int = 0,
        t0: int | None = None,
        t1: int | None = None,
        out_dir: str | Path | None = None,
        roi: Any | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
        sink: DetectionSink | None = None,
    ) -> SequenceDetectionResult:
        """Execute blob detection across frames and route outputs to a DetectionSink.

        When ``sink`` is None:
        - If ``out_dir`` is provided, streams results to disk via ``StreamingDiskDetectionSink``.
        - If ``out_dir`` is None, collects detections in RAM via ``InMemoryDetectionSink``.

        Args:
            czi: Path to CZI file or open CziSource instance.
            channel: Acquisition channel to process (default 0).
            t0: Optional First frame index to process (inclusive, 0-based).
            t1: Optional Last frame index to process (inclusive, 0-based).
            out_dir: Optional Output directory where results are written. Defaults to 'data/processed'.
            roi: Optional Region of Interest specification.
            progress_callback: Optional callable invoked with (completed_frames, total_frames).
            sink: Optional DetectionSink to use for output.

        Returns:
            SequenceDetectionResult containing paths, counts, and metadata.

        """
        source, file_path, resolved_channel, should_close_source = self._resolve_source(czi, channel)
        active_sink: DetectionSink | None = sink

        try:
            info = source.info
            total_available_frames = info.n_t
            start_frame = max(0, t0 if t0 is not None else 0)
            end_frame = min(
                total_available_frames - 1,
                t1 if t1 is not None else total_available_frames - 1,
            )

            frames = list(range(start_frame, end_frame + 1)) if start_frame <= end_frame else []
            chunk_size = self.config.chunk_size
            chunks = [frames[i : i + chunk_size] for i in range(0, len(frames), chunk_size)]

            requested_workers = self.config.workers
            capped_workers, reason = cap_workers(
                requested_workers,
                per_worker_gb=self.config.ram_per_worker_gb,
                ram_fraction=self.config.ram_cap_fraction,
            )
            actual_workers = min(capped_workers, max(1, len(chunks)))

            fmt = self.config.output_format
            if active_sink is None:
                if out_dir is not None:
                    destination_dir = Path(out_dir)
                    destination_dir.mkdir(parents=True, exist_ok=True)
                    stem = stem_of(file_path)
                    output_table_path = table_path(destination_dir, stem, "blobs", fmt)
                    params_file = destination_dir / f"{stem}_blobs_params.json"
                    active_sink = StreamingDiskDetectionSink(
                        output_table_path,
                        params_file,
                        num_frames=len(frames),
                    )
                else:
                    active_sink = InMemoryDetectionSink(num_frames=len(frames))

            time_start = time.time()
            completed_frames = 0

            pp_dict = self.preproc_params.model_dump()
            bp_dict = self.blob_params.model_dump()

            logger.info(
                "Starting sequence detection (%d frames, workers=%d, sink=%s)",
                len(frames),
                actual_workers,
                type(active_sink).__name__,
            )

            if actual_workers <= 1 or len(chunks) <= 1:
                for chunk in chunks:
                    for frame_idx in chunk:
                        detections = detect_frame(
                            source,
                            frame_idx,
                            pp=self.preproc_params,
                            bp=self.blob_params,
                            roi=roi,
                        )
                        prepared = _prepare_frame_detections(detections, frame_idx, info.dt_s)
                        active_sink.on_frame_detections(frame_idx, prepared)
                    completed_frames += len(chunk)
                    if progress_callback is not None:
                        progress_callback(completed_frames, len(frames))
            else:
                with ProcessPoolExecutor(max_workers=actual_workers) as executor:
                    future_to_chunk = {
                        executor.submit(
                            _detect_frames_worker,
                            file_path,
                            resolved_channel,
                            pp_dict,
                            bp_dict,
                            chunk,
                            roi,
                        ): chunk
                        for chunk in chunks
                    }

                    for future in as_completed(future_to_chunk):
                        chunk = future_to_chunk[future]
                        chunk_results = future.result()
                        for fallback_frame, detections in zip(chunk, chunk_results, strict=True):
                            frame_number = (
                                int(detections.iloc[0]["frame"]) if len(detections) > 0 else fallback_frame
                            )
                            prepared = _prepare_frame_detections(detections, frame_number, info.dt_s)
                            active_sink.on_frame_detections(frame_number, prepared)
                        completed_frames += len(chunk_results)
                        if progress_callback is not None:
                            progress_callback(completed_frames, len(frames))

            elapsed_seconds = time.time() - time_start
            info_dict = asdict(info) if is_dataclass(info) else info.__dict__

            metadata: dict[str, Any] = {
                "czi": str(file_path),
                "channel": resolved_channel,
                "t0": start_frame,
                "t1": end_frame,
                "created": datetime.now().isoformat(timespec="seconds"),
                "info": info_dict,
                "preproc": pp_dict,
                "blob": bp_dict,
                "n_blobs": 0,
                "format": fmt,
                "formato": fmt,
                "sorted_by_frame": False,
                "ordinato_per_frame": False,
                "blobs_per_frame_mean": 0.0,
                "elapsed_seconds": round(elapsed_seconds, 2),
                "workers_used": actual_workers,
                "worker_capping_reason": reason,
            }
            return active_sink.finalize(metadata)
        finally:
            if active_sink is not None:
                close_fn = getattr(active_sink, "close", None)
                if callable(close_fn):
                    close_fn()
            if should_close_source:
                source.close()

    def process(
        self,
        czi: str | Path | CziSource,
        channel: int = 0,
        t0: int | None = None,
        t1: int | None = None,
        out_dir: str | Path | None = None,
        roi: Any | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> BatchResult:
        """Execute batch blob detection and stream outputs to disk.

        Args:
            czi: Path to CZI file or open CziSource instance.
            channel: Acquisition channel to process (default 0).
            t0: First frame index to process (inclusive, 0-based).
            t1: Last frame index to process (inclusive, 0-based).
            out_dir: Output directory where results are written. Defaults to 'data/processed'.
            roi: Optional Region of Interest specification.
            progress_callback: Optional callable invoked with (completed_frames, total_frames).

        Returns:
            BatchResult containing paths, counts, and metadata.

        RefactorNote:
            Equivalent of `run` from legacy `batch.py` (lines 76-143).
        """
        seq_result = self.process_sequence(
            czi=czi,
            channel=channel,
            t0=t0,
            t1=t1,
            out_dir=out_dir or Path("data/processed"),
            roi=roi,
            progress_callback=progress_callback,
        )
        assert seq_result.table_path is not None
        assert seq_result.params_path is not None
        return BatchResult(
            table_path=seq_result.table_path,
            params_path=seq_result.params_path,
            num_blobs=seq_result.num_blobs,
            num_frames=seq_result.num_frames,
            metadata=seq_result.metadata,
        )

    def run(
        self,
        czi: str | Path | CziSource,
        channel: int = 0,
        t0: int | None = None,
        t1: int | None = None,
        out_dir: str | Path | None = None,
        roi: Any | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> BatchResult:
        """Alias for process(), matching ParticleLinker conventions."""
        return self.process(
            czi=czi,
            channel=channel,
            t0=t0,
            t1=t1,
            out_dir=out_dir,
            roi=roi,
            progress_callback=progress_callback,
        )


def run_batch(
    czi: str | Path | CziSource,
    channel: int = 0,
    config: BatchConfig | None = None,
    preproc_params: PreprocessingConfig | None = None,
    blob_params: DetectionConfig | None = None,
    t0: int | None = None,
    t1: int | None = None,
    out_dir: str | Path | None = None,
    roi: Any | None = None,
    progress_callback: Callable[[int, int], None] | None = None,
) -> BatchResult:
    """Run batch blob detection and return comprehensive BatchResult.

    Args:
        czi: Path to CZI file or open CziSource instance.
        channel: Channel index to process.
        config: Batch configuration.
        preproc_params: Preprocessing parameters.
        blob_params: Blob detection parameters.
        t0: Starting frame index (inclusive).
        t1: Ending frame index (inclusive).
        out_dir: Output directory.
        roi: Optional ROI bounds or object.
        progress_callback: Progress notification callback.

    Returns:
        BatchResult object.
    """
    processor = BatchProcessor(config=config, preproc_params=preproc_params, blob_params=blob_params)
    return processor.process(
        czi=czi,
        channel=channel,
        t0=t0,
        t1=t1,
        out_dir=out_dir,
        roi=roi,
        progress_callback=progress_callback,
    )


def run(
    czi: str | Path | CziSource,
    channel: int = 0,
    pp: PreprocessingConfig | None = None,
    bp: DetectionConfig | None = None,
    t0: int | None = None,
    t1: int | None = None,
    out_dir: str | Path = Path("data/processed"),
    workers: int = 16,
    chunk: int = 10,
    fmt: str = "parquet",
    roi: Any | None = None,
) -> Path:
    """Legacy-compatible entry point returning the destination table Path.

    RefactorNote:
        Matches signature of `run` from legacy `batch.py` (lines 76-143).
    """
    config = BatchConfig(workers=workers, chunk_size=chunk, output_format=fmt)
    result = run_batch(
        czi=czi,
        channel=channel,
        config=config,
        preproc_params=pp,
        blob_params=bp,
        t0=t0,
        t1=t1,
        out_dir=out_dir,
        roi=roi,
    )
    return result.table_path
