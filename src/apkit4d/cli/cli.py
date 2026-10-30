import click

from apkit4d.cli.commands.batch import batch
from apkit4d.cli.commands.gui import gui
from apkit4d.cli.commands.link import link
from apkit4d.cli.commands.pipeline import pipeline


@click.group()
def cli():
    pass


cli.add_command(gui)
cli.add_command(batch)
cli.add_command(link)
cli.add_command(pipeline)


def main():
    cli()


if __name__ == "__main__":
    main()
