import pathlib

import click


@click.command(help="Execute an analysis pipeline defined in a JSON file.")
@click.argument(
    "pipeline",
    required=False,
    type=click.Path(exists=True, dir_okay=False, path_type=pathlib.Path),
)
@click.option(
    "--list",
    is_flag=True,
    default=False,
    help="List saved pipeline.",
)
@click.option(
    "--only",
    type=click.Choice(["detection", "linking"]),
    default=None,
    help="Execute only a step of the pipeline.",
)
def pipeline(pipeline: str | None, list: bool, only: str | None) -> None:
    # TODO: implement
    pass
