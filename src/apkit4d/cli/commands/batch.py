import pathlib

import click


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
    type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=pathlib.Path),
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
    # TODO: implement
    pass
