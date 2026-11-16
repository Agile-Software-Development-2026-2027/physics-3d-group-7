"""Save detections already produced by the pipeline, without running analysis."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from apkit4d.batching.processor import BatchResult, _json_serializable, stem_of
from apkit4d.io.table import FORMATS, TableWriter, table_path


def save_batch_results(
    detections: pd.DataFrame,
    metadata: dict[str, Any],
    out_dir: Path,
    fmt: str,
    first: int,
    last: int,
    progress: Callable[[int, int], None],
) -> BatchResult:
    """Export a processed frame interval; input metadata uses zero-based inclusive t0/t1.

    The producer supplies czi, channel, t0/t1, acquisition info and actual analysis
    parameters. No source volumes, preprocessing or detection are run here.
    """
    if fmt not in FORMATS:
        raise ValueError(f"Unsupported table format: {fmt}")
    if first < 0 or first > last or first < metadata["t0"] or last > metadata["t1"]:
        raise ValueError("Selected frames are outside the processed interval.")
    if "frame" not in detections:
        raise ValueError("Processed detections must contain a frame column, even when empty.")
    count = int(detections["frame"].between(first, last).sum())
    stem = stem_of(metadata["czi"])
    path = table_path(out_dir, stem, "blobs", fmt)
    writer = TableWriter(path)
    try:
        with writer:
            progress(0, count)
            for start in range(0, len(detections), 100_000):
                chunk = detections.iloc[start : start + 100_000]
                writer.append(chunk[chunk["frame"].between(first, last)])
                progress(writer.n_rows, count)
    except BaseException:
        path.unlink(missing_ok=True)
        raise
    saved = {**metadata, "t0": first, "t1": last, "n_blobs": count, "format": fmt, "formato": fmt}
    params = out_dir / f"{stem}_blobs_params.json"
    params.write_text(json.dumps(saved, indent=2, default=_json_serializable), encoding="utf-8")
    return BatchResult(path, params, count, last - first + 1, saved)
