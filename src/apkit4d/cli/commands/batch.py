import json
import pathlib
from typing import Any

import click

from apkit4d.batching.processor import run_batch
from apkit4d.blob_detection import BlobParams
from apkit4d.core.models import BatchConfig
from apkit4d.preprocessing import PreprocParams


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
    help="Detect blobs on a range of frames of a CZI file, without the GUI. "
    + "The result is a table with one row per blob."
)
@click.argument(
    "czi",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
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
    "--params",
    type=click.STRING,
    help="JSON file with the channel, preprocessing and blob finder parameters. "
    + "If omitted, saved parameters are used, or defaults if none exist.",
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
    help="Format of the output table. Parquet is smaller and faster to read; "
    + "use csv to open the table in other programs.",
)
@click.option(
    "--out",
    type=click.Path(exists=False, dir_okay=True, file_okay=False, path_type=pathlib.Path),
    help="Directory where the results are written. It is created if it does not exist.",
)
def batch(
    czi: pathlib.Path,
    first_frame: int | None,
    last_frame: int | None,
    params: str | None,
    workers: int,
    chunk: int,
    format: str,
    out: pathlib.Path | None,
):
    if workers < 1:
        raise click.BadParameter("Must be at least 1.", param_hint="--workers")

    if chunk < 1:
        raise click.BadParameter("Must be at least 1.", param_hint="--chunk")

    if first_frame is not None and first_frame < 0:
        raise click.BadParameter("Must be non-negative.", param_hint="--first-frame")

    if last_frame is not None and last_frame < 0:
        raise click.BadParameter("Must be non-negative.", param_hint="--last-frame")

    if params is not None:
        try:
            with open(params, encoding="utf-8") as file:
                entry = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise click.ClickException(f"Cannot load parameters from {params}: {exc}") from exc
    else:
        entry = load_saved_params(czi)

    if not isinstance(entry, dict):
        raise click.ClickException("Parameters must be a JSON object.")

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

    batch_config = BatchConfig(
        workers=workers,
        chunk_size=chunk,
        output_format=format,
    )

    preproc_params = PreprocParams.from_dict(entry.get("preproc"))
    blob_params = BlobParams.from_dict(entry.get("blob"))

    result = run_batch(
        czi=czi,
        channel=entry.get("channel", 0),
        config=batch_config,
        preproc_params=preproc_params,
        blob_params=blob_params,
        t0=start,
        t1=end,
        out_dir=out,
    )

    click.echo("Batch processing completed.")
    click.echo(f"Detected blobs: {result.num_blobs}")
    click.echo(f"Processed frames: {result.num_frames}")
    click.echo(f"Output: {result.table_path}")
    click.echo(f"Parameters: {result.params_path}")
