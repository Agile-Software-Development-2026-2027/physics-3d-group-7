I've analyzed [`argparse`](https://docs.python.org/3/library/argparse.html), [`typer`](https://typer.tiangolo.com/), and [`click`](https://click.palletsprojects.com/en/stable/).

`argparse` is already included in the Python standard library, but it is the most verbose option. For example, mapping subparsers to their corresponding functions and splitting subcommands across multiple files requires more code.

`typer` uses type hints to define commands, so the command interface is generated directly from the function signature. However, as we add more options, the function signature can become quite long (even with just two options, it is already quite lengthy). It also doesn't provide a straightforward way to define mutually exclusive options; these must be handled manually, and the documentation must be updated accordingly.

`click` uses decorators to define commands. I prefer this approach over `typer` because each option is defined on its own line, making the code easier to read and allowing long declarations to be split across multiple lines while keeping the function signature readable. It also supports mutually exclusive option groups through the `click-option-group` package. Both `typer` and `click` can be tested conveniently using `CliRunner`.

Some commands, such as `python -m ApKit4D.link`, have options like `--max-dist` and `--max-speed`. When both are provided, `--max-dist` takes precedence and `--max-speed` is ignored. In this case, mutually exclusive options could be used to prevent users from specifying both options at the same time.

Therefore, I think `click` is the best choice.
