"""
`apkit4d pipeline`: analyse a recording without the GUI, or link again the blobs of saved results.

The results are written like the Batch export of the app (`<stem>_blobs`, `<stem>_tracks` and
`<stem>_blobs_params.json`), so they open in the app with `apkit4d gui <json>` or File > Open Results.
"""

import json
import pathlib
from typing import Any

import click

from apkit4d.batching.export import save_tracks
from apkit4d.batching.processor import BatchResult, run_batch
from apkit4d.core.models import BatchConfig, DetectionConfig, PreprocessingConfig, TrackingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.io.saved_results import read_saved_results
from apkit4d.tracking.linker import ParticleLinker

__all__ = ["load_saved_params", "pipeline"]


def load_saved_params(czi: pathlib.Path) -> dict[str, Any]:
    # TODO: Unify the saved parameters path with the gui
    params_file = pathlib.Path("data/app_params.json")
    if not params_file.exists():
        return {}
    try:
        with params_file.open(encoding="utf-8") as file:
            saved_params = json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Cannot load saved parameters: {exc}") from exc
    if not isinstance(saved_params, dict):
        raise click.ClickException("Saved parameters must be a JSON object.")
    stem = czi.stem.replace(" ", "_")
    return saved_params.get(stem, {})


@click.command(
    help="Analyse a recording without the GUI: detect the blobs and link them into tracks. "
    + "FILE is a .czi recording, or the json of saved results (<stem>_blobs_params.json) to link "
    + "its blobs again. The results are written like the Batch export of the app, "
    + "so they open with `apkit4d gui <json>`."
)
@click.argument(
    "file",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
)
@click.option(
    "--params",
    type=click.STRING,
    help="JSON file with the channel, preproc, blob, tracking and roi parameters, like the json of "
    + "saved results. If omitted, saved parameters are used, or defaults if none exist.",
)
@click.option(
    "--first-frame",
    "--fs",
    "first_frame",
    type=click.INT,
    help="First frame to process (0-based, inclusive). "
    + "If omitted, the value from the parameters is used, otherwise 0.",
)
@click.option(
    "--last-frame",
    "--ls",
    "last_frame",
    type=click.INT,
    help="Last frame to process (0-based, inclusive). "
    + "If omitted, the value from the parameters is used, otherwise the last frame of the file.",
)
@click.option(
    "--only",
    type=click.Choice(["detection", "linking"]),
    default=None,
    help="Run only one step: detection on a .czi file, or linking on the json of saved results.",
)
@click.option(
    "--workers",
    type=click.INT,
    default=16,
    show_default=True,
    help="Number of parallel processes. It is reduced automatically if the free RAM is not enough.",
)
@click.option(
    "--chunk",
    type=click.INT,
    default=10,
    show_default=True,
    help="Number of frames assigned to each task.",
)
@click.option(
    "--format",
    type=click.Choice(["parquet", "csv"]),
    default="parquet",
    show_default=True,
    help="Format of the output tables. Parquet is smaller and faster to read; "
    + "use csv to open the tables in other programs.",
)
@click.option(
    "--out",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=pathlib.Path),
    help="Directory where the results of a .czi file are written. It is created if it does not exist. "
    + "If omitted, the directory of the recording.",
)
def pipeline(
    file: pathlib.Path,
    params: str | None,
    first_frame: int | None,
    last_frame: int | None,
    only: str | None,
    workers: int,
    chunk: int,
    format: str,
    out: pathlib.Path | None,
) -> None:
    if workers < 1:
        raise click.BadParameter("Must be at least 1.", param_hint="--workers")
    if chunk < 1:
        raise click.BadParameter("Must be at least 1.", param_hint="--chunk")
    if first_frame is not None and first_frame < 0:
        raise click.BadParameter("Must be non-negative.", param_hint="--first-frame")
    if last_frame is not None and last_frame < 0:
        raise click.BadParameter("Must be non-negative.", param_hint="--last-frame")

    is_saved_results = file.suffix.lower() == ".json"
    if is_saved_results and only == "detection":
        raise click.UsageError("Detection needs the recording: give the .czi file, not the saved results.")
    if not is_saved_results and only == "linking":
        raise click.UsageError("Linking needs detected blobs: give the json of saved results, not the .czi.")

    if params is not None:
        entry = _read_params(params)
    else:
        entry = {} if is_saved_results else load_saved_params(file)
    if not isinstance(entry, dict):
        raise click.ClickException("Parameters must be a JSON object.")

    if is_saved_results:
        _link(file, entry, format)
        return
    config = BatchConfig(workers=workers, chunk_size=chunk, output_format=format)
    result = _detect(file, entry, first_frame, last_frame, config, out)
    if only != "detection":
        _link(result.params_path, entry, format)


def _read_params(params: str) -> Any:
    try:
        with open(params, encoding="utf-8") as file:
            return json.load(file)
    except (OSError, json.JSONDecodeError) as exc:
        raise click.ClickException(f"Cannot load parameters from {params}: {exc}") from exc


def _detect(
    czi: pathlib.Path,
    entry: dict[str, Any],
    first_frame: int | None,
    last_frame: int | None,
    config: BatchConfig,
    out: pathlib.Path | None,
) -> BatchResult:
    """Detect the blobs of `czi` and save them like the Batch export of the app."""
    # Use frame values from CLI if provided otherwise use JSON values
    # Support legacy t0/t1 keys if first_frame/last_frame are missing
    start = first_frame if first_frame is not None else entry.get("first_frame", entry.get("t0", 0))
    end = last_frame if last_frame is not None else entry.get("last_frame", entry.get("t1"))

    if type(start) is not int or start < 0:
        raise click.ClickException("Invalid starting frame.")

    if end is not None:
        if type(end) is not int or end < 0:
            raise click.ClickException("Invalid ending frame.")
        if start > end:
            raise click.UsageError("--first-frame cannot be greater than --last-frame.")

    preproc_entry = entry.get("preproc")
    if preproc_entry is not None and preproc_entry.get("bg_mode", "") == "nessuno":
        preproc_entry["bg_mode"] = "None"
    try:
        preproc_params = PreprocessingConfig(**({} if preproc_entry is None else preproc_entry))
        blob_params = DetectionConfig(**(entry.get("blob") or {}))
        roi = RegionOfInterest.from_dict(entry["roi"]) if entry.get("roi") else None
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"Invalid parameters: {exc}") from exc

    result = run_batch(
        czi=czi,
        channel=entry.get("channel", 0),
        config=config,
        preproc_params=preproc_params,
        blob_params=blob_params,
        t0=start,
        t1=end,
        out_dir=out if out is not None else czi.parent,
        roi=roi,
    )

    click.echo("Detection completed.")
    click.echo(f"Detected blobs: {result.num_blobs}")
    click.echo(f"Processed frames: {result.num_frames}")
    click.echo(f"Output: {result.table_path}")
    click.echo(f"Parameters: {result.params_path}")
    return result


def _link(params_path: pathlib.Path, entry: dict[str, Any], fmt: str) -> None:
    """Link the saved blobs of `params_path` into tracks, saved next to them."""
    try:
        session = read_saved_results(params_path).load_session()
    except (OSError, ValueError) as exc:
        raise click.ClickException(f"Cannot read the saved results {params_path}: {exc}") from exc
    try:
        config = TrackingConfig(**entry["tracking"]) if entry.get("tracking") else session.tracking_config
    except (TypeError, ValueError) as exc:
        raise click.ClickException(f"Invalid tracking parameters: {exc}") from exc
    config = config or TrackingConfig()

    assert session.blobs is not None  # saved results always come back with their blobs table
    dt_s = (session.metadata or {}).get("info", {}).get("dt_s")
    result = ParticleLinker(config).link(session.blobs, dt_s=dt_s)
    tracks_path = save_tracks(params_path, result.tracks, config, fmt)

    click.echo("Linking completed.")
    click.echo(f"Tracks: {result.metadata.get('num_tracks_retained', 0)}")
    click.echo(f"Output: {tracks_path}")
    click.echo(f"Open the results with: apkit4d gui {params_path}")
