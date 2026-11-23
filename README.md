# ApKit4D

An application for visualizing and analyzing 4D (3D space + time) microscopy recordings of swimming algae taken in the Zeiss [`.czi`](https://www.zeiss.com/microscopy/en/products/software/zeiss-zen/czi-image-file-format.html) format. The microorganisms are detected in 3D, their trajectories tracked across frames in order to perform a motility analysis and to extract metrics.

<!-- TODO: put a fancy screenshot of the app here -->

## Getting started

First, clone this repository with `git clone https://github.com/Agile-Software-Development-2026-2027/physics-3d-group-7.git`. Make sure to run the following commands in the cloned repository.

The app can be run with [uv](https://docs.astral.sh/uv/getting-started/installation/), via the command `uv run apkit4d`, or with standard Python:

```bash
python -m venv .venv # create a Python virtual environment
source .venv/bin/activate # activate the venv
python -m pip install --upgrade pip # install pip itself
python -m pip install . # install the project's dependencies
python -m apkit4d # run the app
# execute 'deactivate` to leave the venv
```

Running the app will show its usage:

```
Usage: python -m apkit4d [OPTIONS] COMMAND [ARGS]...

Options:
  --help  Show this message and exit.

Commands:
  batch     Detect blobs on a range of frames of a CZI file, without the...
  gui       Open the ApKit4D window.
  link      Link the blobs found by `batch` into tracks.
  pipeline  Execute an analysis pipeline defined in a JSON file.
```

> [!TIP]
> Use `--help` with a subcommand to show what it accepts, e.g. `python -m apkit4d pipeline --help`.

## How we work

- `main` is protected: nobody can push to it, every change goes through a pull request.
- Branches are short-lived (less than a day) and pull requests are small (less than 200 lines).
- A pull request needs the approval of a teammate and a green CI, and must be up to date with
  `main`. It is merged with a squash merge.
- The backlog and the sprints are on the Jira board of the team, not in this repository.
- The title of a pull request starts with the key of the Jira issue it implements:
  `ABC-12 Add the login form`.
- If `main` is red, fixing it comes before anything else.

## CI

`.github/workflows/ci.yml` runs on every pull request. It starts empty and always passes: add
the steps that build and test the project as soon as there is something to test.
