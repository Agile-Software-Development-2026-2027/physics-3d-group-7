import click


def get_argument(command: click.Command, name: str) -> click.Argument:
    return next(p for p in command.params if isinstance(p, click.Argument) and p.name == name)


def get_option(command: click.Command, name: str) -> click.Option:
    return next(p for p in command.params if isinstance(p, click.Option) and name in p.opts)


def is_param_defined(command: click.Command, name: str) -> bool:
    for p in command.params:
        if isinstance(p, click.Argument) and p.name == name:
            return True

        if isinstance(p, click.Option) and name in p.opts:
            return True

    return False
