"""Prepare real blob detections for trajectory linking."""

from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import pandas as pd

from apkit4d.batching.processor import BatchProcessor
from apkit4d.core.models import BatchConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.detection.blob_detection import BlobParams
from apkit4d.detection.preprocessing import PreprocParams
from apkit4d.io.czi import CziSource
from apkit4d.io.table import read_table


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
) -> DetectionData:
    """Detect all frames, reusing an open CziSource when given."""
    processor = BatchProcessor(
        config=BatchConfig(workers=1),
        preproc_params=preproc_params,
        blob_params=blob_params,
    )

    with TemporaryDirectory() as output_dir:
        result = processor.process(
            czi,
            out_dir=output_dir,
            roi=roi,
        )

        if result.num_blobs:
            detections = read_table(result.table_path)
        else:
            detections = pd.DataFrame(columns=["frame", "z_um", "y_um", "x_um"])

    return DetectionData(
        detections=detections,
        dt_s=result.metadata.get("info", {}).get("dt_s"),
        metadata=result.metadata,
    )
