import click

from apkit4d.cli.commands.batch import batch
from apkit4d.cli.commands.gui import gui
from apkit4d.cli.commands.link import link


@click.group()
def cli():
    pass


cli.add_command(gui)
cli.add_command(batch)
cli.add_command(link)


def main():
    cli()


if __name__ == "__main__":
    main()
