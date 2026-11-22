"""Save detections already produced by the pipeline, without running analysis."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pandas as pd

from apkit4d.batching.processor import BatchResult, stem_of
from apkit4d.core.models import TrackingConfig
from apkit4d.io.saved_results import PARAMS_SUFFIX
from apkit4d.io.table import FORMATS, TableWriter, table_path, write_table
from apkit4d.pipeline.sinks import json_serializable


def save_batch_results(
    detections: pd.DataFrame,
    metadata: dict[str, Any],
    out_dir: Path,
    fmt: str,
    first: int,
    last: int,
    progress: Callable[[int, int], None],
    tracks: pd.DataFrame | None = None,
    tracking_config: TrackingConfig | None = None,
) -> BatchResult:
    """Export a processed frame interval; input metadata uses zero-based inclusive t0/t1.

    The producer supplies czi, channel, t0/t1, acquisition info and actual analysis
    parameters. No source volumes, preprocessing or detection are run here.
    Linked tracks, when given, are saved for the same frames next to the blobs, with the
    tracking configuration that produced them.
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
    # the names of the tables let `apkit4d.io.saved_results` read them back (no blobs, no table)
    saved["table"] = path.name if count else None
    saved["tracks_table"] = None
    if tracks is not None:
        tracks_path = table_path(out_dir, stem, "tracks", fmt)
        try:
            write_table(tracks[tracks["frame"].between(first, last)], tracks_path)
        except BaseException:
            tracks_path.unlink(missing_ok=True)
            raise
        saved["tracks_table"] = tracks_path.name
    if tracking_config is not None:
        saved["tracking"] = tracking_config.model_dump()
    params = out_dir / f"{stem}{PARAMS_SUFFIX}"
    params.write_text(json.dumps(saved, indent=2, default=json_serializable), encoding="utf-8")
    return BatchResult(path, params, count, last - first + 1, saved)
