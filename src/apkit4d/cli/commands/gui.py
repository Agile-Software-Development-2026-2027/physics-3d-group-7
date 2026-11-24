from pathlib import Path

import click


@click.command(
    help="Open the ApKit4D window. If FILE is given it is opened at startup: a .czi recording, "
    + "or the json of saved results (<stem>_blobs_params.json), shown on their recording."
)
@click.argument(
    "file",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--mock",
    is_flag=True,
    default=False,
    help="Launch the GUI with a synthetic mock algae dataset (no CZI file required).",
)
def gui(file: Path | None, mock: bool):
    from apkit4d.gui.app import run

    if file is not None and mock:
        raise click.UsageError("Cannot specify both a file and --mock.")
    run(file, mock=mock)
