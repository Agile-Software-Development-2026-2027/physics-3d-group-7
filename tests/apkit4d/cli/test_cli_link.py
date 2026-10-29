import pathlib

import click
import pytest
from click._utils import UNSET
from click.testing import CliRunner

from apkit4d.cli.cli import cli
from tests.apkit4d.cli.helper import get_argument, get_option, is_param_defined

LINK = cli.commands["link"]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def blobs(tmp_path: pathlib.Path) -> pathlib.Path:
    f = tmp_path / "sample_blobs.parquet"
    _ = f.write_bytes(b"")
    return f


def test_apkit4d_link_is_defined(runner: CliRunner):
    result = runner.invoke(cli, ["link", "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "param",
    [
        "blobs",
        "--max-dist",
        "--max-speed",
        "--max-gap",
        "--gap-dist",
        "--min-len",
        "--format",
        "--resamples",
        "--min-reliability",
        "--out",
        "--t0",
        "--t1",
        "--roi-um",
        "--label",
        "--format",
    ],
)
def test_apkit4d_link_has_params_defined(param: str):
    assert is_param_defined(LINK, param)


def test_blobs_is_a_path_and_an_obligatory_argument():
    arg = get_argument(LINK, "blobs")
    assert arg.required
    assert arg.nargs == 1
    assert isinstance(arg.type, click.Path)
    assert arg.type.type is pathlib.Path
    assert arg.type.exists
    assert not arg.type.dir_okay


def test_max_dist_is_an_optional_float():
    opt = get_option(LINK, "--max-dist")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_max_speed_is_an_optional_float_with_default_250():
    opt = get_option(LINK, "--max-speed")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default == 250.0


def test_max_gap_is_an_optional_int_with_default_3():
    opt = get_option(LINK, "--max-gap")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default == 3


def test_gap_dist_is_an_optional_float():
    opt = get_option(LINK, "--gap-dist")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_min_len_is_an_optional_int_with_default_3():
    opt = get_option(LINK, "--min-len")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default == 3


def test_resamples_is_an_optional_int_with_default_20():
    opt = get_option(LINK, "--resamples")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default == 20


def test_min_reliability_is_an_optional_float_with_default_0():
    opt = get_option(LINK, "--min-reliability")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default == 0.0


def test_out_is_an_optional_dir():
    opt = get_option(LINK, "--out")
    assert isinstance(opt.type, click.Path)
    assert opt.type.type is pathlib.Path
    assert opt.type.dir_okay
    assert not opt.type.file_okay
    assert not opt.required
    assert opt.default is UNSET


def test_t0_is_an_optional_int():
    opt = get_option(LINK, "--t0")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_t1_is_an_optional_int():
    opt = get_option(LINK, "--t1")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_roi_um_is_an_optional_string():
    opt = get_option(LINK, "--roi-um")
    assert isinstance(opt.type, click.types.StringParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_label_is_an_optional_string_with_default_empty_string():
    opt = get_option(LINK, "--label")
    assert isinstance(opt.type, click.types.StringParamType)
    assert not opt.required
    assert opt.default == ""


def test_format_is_an_optional_choice():
    opt = get_option(LINK, "--format")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["parquet", "csv"]
    assert not opt.required
    assert opt.default is UNSET
