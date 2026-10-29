import pathlib

import click


@click.command(
    help="Link the blobs found by `batch` into tracks. "
    + "The output is a tracks table, a per-track statistics table (always csv), "
    + "a diagnostic figure and a json file with the parameters used."
)
@click.argument(
    "blobs",
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
)
@click.option(
    "--max-dist",
    type=click.FLOAT,
    help="Search radius between consecutive frames, in micrometers. "
    + "Takes precedence over --max-speed. "
    + "If omitted, it is --max-speed times the frame interval of the file "
    + "(20 um if the interval is unknown).",
)
@click.option(
    "--max-speed",
    type=click.FLOAT,
    default=250.0,
    show_default=True,
    help="Maximum expected speed in um/s, used to derive the search radius. "
    + "Ignored if --max-dist is given.",
)
@click.option(
    "--max-gap",
    type=click.INT,
    default=3,
    show_default=True,
    help="Maximum number of missing frames that can be bridged inside a track.",
)
@click.option(
    "--gap-dist",
    type=click.FLOAT,
    help="Search radius per skipped frame when bridging gaps, in micrometers. "
    + "If omitted, it is 1.25 times the search radius.",
)
@click.option(
    "--min-len",
    type=click.INT,
    default=3,
    show_default=True,
    help="Minimum number of points needed to keep a track.",
)
@click.option(
    "--resamples",
    type=click.INT,
    default=20,
    show_default=True,
    help="Number of resamples used to estimate the reliability of each link. "
    + "0 skips the estimate (faster).",
)
@click.option(
    "--min-reliability",
    type=click.FLOAT,
    default=0.0,
    show_default=True,
    help="Drop the tracks whose mean reliability is below this value. "
    + "0 keeps all of them. It needs --resamples greater than 0.",
)
@click.option(
    "--out",
    type=click.Path(file_okay=False, dir_okay=True, path_type=pathlib.Path),
    help="Directory where the results are written (created if missing). "
    + "If omitted, the directory of the blobs table is used.",
)
@click.option(
    "--t0",
    type=click.INT,
    help="First frame to link (0-based, inclusive). If omitted, the first frame of the table.",
)
@click.option(
    "--t1",
    type=click.INT,
    help="Last frame to link (0-based, inclusive). If omitted, the last frame of the table.",
)
@click.option(
    "--roi-um",
    type=click.STRING,
    help="Spatial crop in micrometers: six comma-separated numbers, " + "Z0,Z1,Y0,Y1,X0,X1, without spaces.",
)
@click.option(
    "--label",
    type=click.STRING,
    default="",
    help="Suffix added to the names of the output files, " + "to avoid overwriting a previous linking.",
)
@click.option(
    "--format",
    type=click.Choice(["parquet", "csv"]),
    help="Format of the tracks table. If omitted, the same as the blobs table.",
)
def link(
    blobs: pathlib.Path,
    max_dist: float | None,
    max_speed: float,
    max_gap: int,
    gap_dist: float | None,
    min_len: int,
    resamples: int,
    min_reliability: float,
    out: pathlib.Path | None,
    t0: int | None,
    t1: int | None,
    roi_um: str | None,
    label: str,
    format: str | None,
) -> None:
    # TODO: implement
    pass
