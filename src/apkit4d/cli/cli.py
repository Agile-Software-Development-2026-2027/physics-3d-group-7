import click

from apkit4d.cli.commands.gui import gui


@click.group()
def cli():
    pass


cli.add_command(gui)


def main():
    cli()


if __name__ == "__main__":
    main()
