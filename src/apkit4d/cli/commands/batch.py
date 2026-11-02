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
    "--t0",
    type=click.INT,
    help="First frame to process (0-based, inclusive). "
    + "If omitted, the value from the parameters is used, otherwise 0.",
)
@click.option(
    "--t1",
    type=click.INT,
    help="Last frame to process (0-based, inclusive). "
    + "If omitted, the value from the parameters is used, otherwise the last frame of the file.",
)
@click.option(
    "--params",
    type=click.STRING,
    help="JSON file with the channel, preprocessing and blob finder parameters. "
    + "If omitted, the parameters saved for this file are used.",
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
    help="Existing directory where the results are written.",
)
def batch(
    czi: pathlib.Path,
    t0: int | None,
    t1: int | None,
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

    if t0 is not None and t0 < 0:
        raise click.BadParameter("Must be non-negative.", param_hint="--t0")

    if t1 is not None and t1 < 0:
        raise click.BadParameter("Must be non-negative.", param_hint="--t1")

    if params is not None:
        try:
            with open(params, encoding="utf-8") as file:
                entry = json.load(file)
        except (OSError, json.JSONDecodeError) as exc:
            raise click.ClickException(f"Cannot load parameters from {params}: {exc}") from exc
    else:
        entry = load_saved_params(czi)
        if not entry:
            raise click.ClickException(f"No saved parameters for {czi.name}. Provide --params.")

    if not isinstance(entry, dict):
        raise click.ClickException("Parameters must be a JSON object.")

    start = t0 if t0 is not None else entry.get("t0", 0)
    end = t1 if t1 is not None else entry.get("t1")

    if type(start) is not int or start < 0:
        raise click.ClickException("Invalid starting frame.")

    if end is not None:
        if type(end) is not int or end < 0:
            raise click.ClickException("Invalid ending frame.")
        if start > end:
            raise click.UsageError("--t0 cannot be greater than --t1.")

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
