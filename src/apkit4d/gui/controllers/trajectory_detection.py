"""Prepare real blob detections for trajectory linking."""

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from apkit4d.batching.processor import BatchProcessor
from apkit4d.core.models import BatchConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.detection.blob_detection import BlobParams
from apkit4d.detection.preprocessing import PreprocParams
from apkit4d.io.czi import CziSource
from apkit4d.io.table import read_table
from apkit4d.pipeline.contracts import DetectionSink


@dataclass(frozen=True)
class DetectionData:
    detections: pd.DataFrame
    dt_s: float | None
    metadata: dict[str, Any]


def detect_sequence(
    czi: str | Path | CziSource,
    preproc_params: PreprocParams,
    blob_params: BlobParams,
    roi: RegionOfInterest | None = None,
    *,
    workers: int = 1,
    out_dir: str | Path | None = None,
    sink: DetectionSink | None = None,
) -> DetectionData:
    """Detect blobs across all frames in a sequence.

    Defaults to in-memory collection without disk writes; streams to disk when
    ``out_dir`` or a disk-backed ``sink`` is provided.

    Args:
        czi: Path to a CZI file or an already-open ``CziSource`` instance.
        preproc_params: Volume preprocessing parameters.
        blob_params: LoG blob detection parameters.
        roi: Optional region of interest restricting detection bounds.
        workers: Number of worker processes to request for frame processing.
        out_dir: Optional directory for streaming detections to disk instead of RAM.
        sink: Optional custom ``DetectionSink`` overriding default sink selection.

    Returns:
        DetectionData containing the detections DataFrame, frame interval
        ``dt_s``, and sequence metadata dictionary.
    """
    processor = BatchProcessor(
        config=BatchConfig(workers=workers),
        preproc_params=preproc_params,
        blob_params=blob_params,
    )
    result = processor.process_sequence(
        czi,
        out_dir=out_dir,
        roi=roi,
        sink=sink,
    )
    if result.detections is not None:
        detections = result.detections
    elif result.table_path is not None and result.num_blobs > 0:
        detections = read_table(result.table_path)
    else:
        detections = pd.DataFrame(columns=["frame", "z_um", "y_um", "x_um"])

    return DetectionData(
        detections=detections,
        dt_s=result.metadata.get("info", {}).get("dt_s"),
        metadata=result.metadata,
    )
