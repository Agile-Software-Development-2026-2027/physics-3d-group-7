import pathlib

import click

from apkit4d.cli.constants import CZI_METAVAR


@click.command()
@click.argument(
    "czi", type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path), metavar=CZI_METAVAR
)
@click.option("--t0", type=click.INT)
@click.option("--t1", type=click.INT)
@click.option("--params", type=click.STRING)
@click.option("--workers", type=click.INT, default=16)
@click.option("--chunk", type=click.INT, default=10)
@click.option("--format", type=click.Choice(["parquet", "csv"]), default="parquet")
@click.option("--out", type=click.Path(exists=True, dir_okay=True, file_okay=False, path_type=pathlib.Path))
def batch():
    # TODO: implement
    pass
