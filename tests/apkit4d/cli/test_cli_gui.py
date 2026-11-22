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


@pytest.mark.parametrize("param", ["file", "--mock"])
def test_apkit4d_gui_has_params_defined(param: str):
    assert is_param_defined(GUI, param)


def test_mock_is_a_flag_with_default_false():
    opt = get_option(GUI, "--mock")
    assert opt.is_flag
    assert isinstance(opt.type, click.types.BoolParamType)
    assert opt.default is False


def test_file_is_an_optional_path_argument_with_default_none():
    arg = get_argument(GUI, "file")
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


def test_gui_mock_flag_runs_with_mock_true(runner: CliRunner, fake_gui: MagicMock):
    r = runner.invoke(cli, ["gui", "--mock"])
    assert r.exit_code == 0
    fake_gui.run.assert_called_once_with(None, mock=True)


def test_gui_rejects_czi_with_mock_flag(runner: CliRunner, fake_gui: MagicMock, tmp_path: pathlib.Path):  # pyright: ignore[reportUnusedParameter]
    czi = tmp_path / "sample.czi"
    _ = czi.write_bytes(b"")
    r = runner.invoke(cli, ["gui", str(czi), "--mock"])
    assert r.exit_code == 2
    assert "Cannot specify both" in r.output


def test_gui_opens_saved_results_too(runner: CliRunner, fake_gui: MagicMock, tmp_path: pathlib.Path):
    results = tmp_path / "sample_blobs_params.json"
    _ = results.write_text("{}", encoding="utf-8")
    r = runner.invoke(cli, ["gui", str(results)])
    assert r.exit_code == 0
    fake_gui.run.assert_called_once_with(results, mock=False)


def test_gui_has_no_unused_flags():
    assert not is_param_defined(GUI, "--software-gl")
    assert not is_param_defined(GUI, "--diagnostic")
