## CLI

Use [`click`](https://click.palletsprojects.com/en/stable/) to implement command-line interfaces.

`click` was chosen over [`argparse`](https://docs.python.org/3/library/argparse.html) and [`typer`](https://typer.tiangolo.com/) because it maps commands directly onto functions through decorators, so the function signature stays readable and each option sits on its own line (long definitions can be wrapped without affecting the rest). It also supports mutually exclusive options through `click-option-group` and makes commands easy to [test with `CliRunner`](https://click.palletsprojects.com/en/stable/testing/).