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
from apkit4d.pipeline.sinks import InMemoryDetectionSink


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
) -> DetectionData:
    """Detect all frames in memory, reusing an open CziSource when given."""
    processor = BatchProcessor(
        config=BatchConfig(workers=workers),
        preproc_params=preproc_params,
        blob_params=blob_params,
    )
    result = processor.process_sequence(
        czi,
        roi=roi,
        sink=InMemoryDetectionSink(),
    )
    detections = (
        result.detections
        if result.detections is not None
        else pd.DataFrame(columns=["frame", "z_um", "y_um", "x_um"])
    )

    return DetectionData(
        detections=detections,
        dt_s=result.metadata.get("info", {}).get("dt_s"),
        metadata=result.metadata,
    )
