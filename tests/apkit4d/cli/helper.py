import click


def get_argument(command, name) -> click.Argument:
    return next(p for p in command.params if isinstance(p, click.Argument) and p.name == name)


def get_option(command, name) -> click.Option:
    return next(p for p in command.params if isinstance(p, click.Option) and name in p.opts)


def is_param_defined(command, name) -> bool:
    for p in command.params:
        if isinstance(p, click.Argument) and p.name == name:
            return True

        if isinstance(p, click.Option) and name in p.opts:
            return True

    return False
