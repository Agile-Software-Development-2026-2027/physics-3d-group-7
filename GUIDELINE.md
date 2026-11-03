## CLI

Use [`click`](https://click.palletsprojects.com/en/stable/) to implement command-line interfaces.

`click` was chosen over [`argparse`](https://docs.python.org/3/library/argparse.html) and [`typer`](https://typer.tiangolo.com/) because it maps commands directly onto functions through decorators, so the function signature stays readable and each option sits on its own line (long definitions can be wrapped without affecting the rest). It also supports mutually exclusive options through `click-option-group` and makes commands easy to [test with `CliRunner`](https://click.palletsprojects.com/en/stable/testing/).

## Documenting code

Refer to the [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings) for guidelines to follow when documenting modules, functions and classes.

## Types in Python

Try to have the most specific and strict values for the type of any value. This, in combination with tools such as `ty`, can help us avoid runtime bugs.

It is usually not necessary to specify the type of a local variable, as it should be inferred by the type checker. The types in function signatures **must** be fully explicit. Class fields too.
