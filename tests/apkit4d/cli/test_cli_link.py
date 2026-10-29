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


def test_blobs_is_a_path_and_an_obligatory_argument():
    assert is_param_defined(LINK, "blobs")
    arg = get_argument(LINK, "blobs")
    assert arg.required
    assert arg.nargs == 1
    assert isinstance(arg.type, click.Path)
    assert arg.type.type is pathlib.Path
    assert arg.type.exists
    assert not arg.type.dir_okay


def test_max_dist_is_an_optional_float():
    assert is_param_defined(LINK, "--max-dist")
    opt = get_option(LINK, "--max-dist")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_max_speed_is_an_optional_float_with_default_250():
    assert is_param_defined(LINK, "--max-speed")
    opt = get_option(LINK, "--max-speed")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default == 250.0


def test_max_gap_is_an_optional_int_with_default_3():
    assert is_param_defined(LINK, "--max-gap")
    opt = get_option(LINK, "--max-gap")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default == 3


def test_gap_dist_is_an_optional_float():
    assert is_param_defined(LINK, "--gap-dist")
    opt = get_option(LINK, "--gap-dist")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_min_len_is_an_optional_int_with_default_3():
    assert is_param_defined(LINK, "--min-len")
    opt = get_option(LINK, "--min-len")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default == 3


def test_resamples_is_an_optional_int_with_default_20():
    assert is_param_defined(LINK, "--resamples")
    opt = get_option(LINK, "--resamples")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default == 20


def test_min_reliability_is_an_optional_float_with_default_0():
    assert is_param_defined(LINK, "--min-reliability")
    opt = get_option(LINK, "--min-reliability")
    assert isinstance(opt.type, click.types.FloatParamType)
    assert not opt.required
    assert opt.default == 0.0


def test_out_is_an_optional_dir():
    assert is_param_defined(LINK, "--out")
    opt = get_option(LINK, "--out")
    assert isinstance(opt.type, click.Path)
    assert opt.type.type is pathlib.Path
    assert opt.type.dir_okay
    assert not opt.type.file_okay
    assert not opt.required
    assert opt.default is UNSET


def test_t0_is_an_optional_int():
    assert is_param_defined(LINK, "--t0")
    opt = get_option(LINK, "--t0")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_t1_is_an_optional_int():
    assert is_param_defined(LINK, "--t1")
    opt = get_option(LINK, "--t1")
    assert isinstance(opt.type, click.types.IntParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_roi_um_is_an_optional_string():
    assert is_param_defined(LINK, "--roi-um")
    opt = get_option(LINK, "--roi-um")
    assert isinstance(opt.type, click.types.StringParamType)
    assert not opt.required
    assert opt.default is UNSET


def test_label_is_an_optional_string_with_default_empty_string():
    assert is_param_defined(LINK, "--label")
    opt = get_option(LINK, "--label")
    assert isinstance(opt.type, click.types.StringParamType)
    assert not opt.required
    assert opt.default == ""


def test_format_is_an_optional_choice():
    assert is_param_defined(LINK, "--format")
    opt = get_option(LINK, "--format")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["parquet", "csv"]
    assert not opt.required
    assert opt.default is UNSET
