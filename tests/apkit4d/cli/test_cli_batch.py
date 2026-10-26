import pathlib

import click
import pytest
from click.testing import CliRunner

from apkit4d.cli.cli import cli
from tests.apkit4d.cli.helper import get_argument, get_option, is_param_defined

BATCH = cli.commands["batch"]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_apkit4d_batch_is_defined(runner: CliRunner):
    result = runner.invoke(cli, ["batch", "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "param", ["czi", "--params", "--t0", "--t1", "--out", "--workers", "--chunk", "--format"]
)
def test_apkit4d_batch_has_params_defined(param: str):
    assert is_param_defined(BATCH, param)


def test_czi_is_a_path_and_an_obligatory_argument():
    arg = get_argument(BATCH, "czi")
    assert arg.required
    assert arg.nargs == 1
    assert isinstance(arg.type, click.Path)
    assert arg.type.type is pathlib.Path
    assert arg.type.exists
    assert not arg.type.dir_okay


def test_t0_is_an_option_and_an_int():
    opt = get_option(BATCH, "--t0")
    assert isinstance(opt.type, click.types.IntParamType)


def test_t1_is_an_option_and_an_int():
    opt = get_option(BATCH, "--t1")
    assert isinstance(opt.type, click.types.IntParamType)


def test_out_is_an_option_and_a_dir():
    opt = get_option(BATCH, "--out")
    assert isinstance(opt.type, click.Path)
    assert opt.type.type is pathlib.Path
    assert opt.type.dir_okay
    assert not opt.type.file_okay


def test_workers_is_an_option_and_an_int():
    opt = get_option(BATCH, "--workers")
    assert isinstance(opt.type, click.types.IntParamType)


def test_chunk_is_an_option_and_an_int():
    opt = get_option(BATCH, "--chunk")
    assert isinstance(opt.type, click.types.IntParamType)


def test_format_is_an_option_and_an_choice():
    opt = get_option(BATCH, "--format")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["parquet", "csv"]


def test_params_is_an_option_and_a_string():
    opt = get_option(BATCH, "--params")
    assert isinstance(opt.type, click.types.StringParamType)
