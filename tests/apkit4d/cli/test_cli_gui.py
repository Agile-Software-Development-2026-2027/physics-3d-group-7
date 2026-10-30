import pathlib
import sys
from unittest.mock import MagicMock

import click
import pytest
from click.testing import CliRunner

from apkit4d.cli.cli import cli
from tests.apkit4d.cli.helper import get_argument, get_option, is_param_defined

GUI = cli.commands["gui"]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def fake_gui(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    fake = MagicMock()
    monkeypatch.setitem(sys.modules, "apkit4d.gui.app", fake)
    return fake


# fake_gui is needed only for executing the fixture
def test_apkit4d_gui_is_defined(runner: CliRunner, fake_gui: MagicMock):  # pyright: ignore[reportUnusedParameter]
    result = runner.invoke(cli, ["gui", "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize("param", ["czi", "--software-gl", "--diagnostic"])
def test_apkit4d_gui_has_params_defined(param: str):
    assert is_param_defined(GUI, param)


@pytest.mark.parametrize("option", ["--software-gl", "--diagnostic"])
def test_gui_options_are_flags_with_default_false(option: str):
    opt = get_option(GUI, option)
    assert opt.is_flag
    assert isinstance(opt.type, click.types.BoolParamType)
    assert opt.default is False


def test_czi_is_an_optional_path_argument_with_default_none():
    arg = get_argument(GUI, "czi")
    assert not arg.required
    assert arg.nargs == 1
    assert isinstance(arg.type, click.Path)
    assert arg.type.type is pathlib.Path
    assert arg.type.exists
    assert not arg.type.dir_okay
    assert arg.default is None


# fake_gui is needed only for executing the fixture
def test_gui_rejects_two_files(runner: CliRunner, fake_gui: MagicMock, tmp_path: pathlib.Path):  # pyright: ignore[reportUnusedParameter]
    a, b = tmp_path / "a.czi", tmp_path / "b.czi"
    _ = a.write_bytes(b"")
    _ = b.write_bytes(b"")
    r = runner.invoke(cli, ["gui", str(a), str(b)])
    assert r.exit_code == 2
