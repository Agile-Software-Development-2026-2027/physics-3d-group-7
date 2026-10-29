import pathlib

import click
import pytest
from click.testing import CliRunner

from apkit4d.cli.cli import cli
from tests.apkit4d.cli.helper import get_argument, get_option, is_param_defined

PIPELINE = cli.commands["pipeline"]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_apkit4d_pipeline_is_defined(runner: CliRunner):
    result = runner.invoke(cli, ["pipeline", "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("param", ["pipeline", "--list", "--only"])
def test_apkit4d_pipeline_has_params_defined(param: str):
    assert is_param_defined(PIPELINE, param)


def test_pipeline_is_an_optional_path_argument():
    arg = get_argument(PIPELINE, "pipeline")
    assert not arg.required
    assert arg.nargs == 1
    assert isinstance(arg.type, click.Path)
    assert arg.type.type is pathlib.Path
    assert arg.type.exists
    assert arg.type.file_okay
    assert not arg.type.dir_okay


def test_list_is_an_optional_flag():
    opt = get_option(PIPELINE, "--list")
    assert opt.is_flag
    assert not opt.required
    assert opt.default is False


def test_only_is_an_optional_choice():
    opt = get_option(PIPELINE, "--only")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["detection", "linking"]
    assert not opt.required
    assert opt.default is None
