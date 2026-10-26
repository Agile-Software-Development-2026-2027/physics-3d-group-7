import sys
import types

import click
import pytest
from click.testing import CliRunner
from helper import get_argument, get_option, is_param_defined

from apkit4d.cli.cli import cli


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_gui(monkeypatch):
    calls = []
    fake = types.ModuleType("ApKit4D.gui")
    fake.run = lambda *a, **k: calls.append((a, k))
    monkeypatch.setitem(sys.modules, "ApKit4D.gui", fake)
    return calls


def test_apkit4d_gui_is_defined(runner, fake_gui):
    result = runner.invoke(cli, ["gui", "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("param", ["czi", "--software-gl", "--diagnostic"])
def test_apkit4d_gui_has_params_defined(runner, param):
    assert is_param_defined(cli.commands["gui"], param)


@pytest.mark.parametrize("option", ["--software-gl", "--diagnostic"])
def test_gui_options_are_flags(option):
    opt = get_option(cli.commands["gui"], option)
    assert opt.is_flag
    assert isinstance(opt.type, click.types.BoolParamType)


def test_czi_is_an_optional_path_argument():
    arg = get_argument(cli.commands["gui"], "czi")
    assert not arg.required
    assert arg.nargs == 1
    assert isinstance(arg.type, click.Path)
    assert arg.type.exists
    assert not arg.type.dir_okay


def test_gui_rejects_two_files(runner, fake_gui, tmp_path):
    a, b = tmp_path / "a.czi", tmp_path / "b.czi"
    a.write_bytes(b"")
    b.write_bytes(b"")
    r = runner.invoke(cli, ["gui", str(a), str(b)])
    assert r.exit_code == 2
