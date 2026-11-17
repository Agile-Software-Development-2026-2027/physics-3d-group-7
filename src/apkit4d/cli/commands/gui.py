from pathlib import Path

import click


@click.command(help="Open the ApKit4D window. If CZI is given, the file is loaded at startup.")
@click.argument(
    "czi",
    required=False,
    default=None,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
)
@click.option(
    "--software-gl",
    is_flag=True,
    default=False,
    help="Render with software OpenGL (Mesa) instead of the GPU (slower in 3D). "
    + "Use it when the NVIDIA driver cannot create a context. ",
)
@click.option(
    "--diagnostic",
    is_flag=True,
    default=False,
    help="Log every GUI freeze longer than 1 second to ApKit4D_blocchi.log, "
    + "with the line of code responsible.",
)
@click.option(
    "--mock",
    is_flag=True,
    default=False,
    help="Launch the GUI with a synthetic mock algae dataset (no CZI file required).",
)
def gui(czi: Path | None, software_gl: bool, diagnostic: bool, mock: bool):
    from apkit4d.gui.app import run

    if czi is not None and mock:
        raise click.UsageError("Cannot specify both a CZI file and --mock.")
    run(czi, mock=mock)
