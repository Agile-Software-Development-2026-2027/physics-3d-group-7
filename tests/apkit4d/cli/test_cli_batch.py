import pathlib
from types import SimpleNamespace
from unittest.mock import patch

import click
import pytest
from click._utils import UNSET
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
    "param",
    ["czi", "--params", "--first-frame", "--last-frame", "--out", "--workers", "--chunk", "--format"],
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


def test_first_frame_is_an_option_and_an_int():
    opt = get_option(BATCH, "--first-frame")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default is UNSET


def test_last_frame_is_an_option_and_an_int():
    opt = get_option(BATCH, "--last-frame")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default is UNSET


def test_out_is_an_option_and_a_dir():
    opt = get_option(BATCH, "--out")
    assert isinstance(opt.type, click.Path)
    assert opt.type.type is pathlib.Path
    assert opt.type.dir_okay
    assert not opt.type.file_okay
    assert opt.default is UNSET


def test_workers_is_an_option_and_an_int_with_default_16():
    opt = get_option(BATCH, "--workers")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default == 16


def test_chunk_is_an_option_and_an_int_with_default_10():
    opt = get_option(BATCH, "--chunk")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default == 10


def test_format_is_an_option_and_an_choice_with_default_parquet():
    opt = get_option(BATCH, "--format")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["parquet", "csv"]
    assert opt.default == "parquet"


def test_params_is_an_option_and_a_string():
    opt = get_option(BATCH, "--params")
    assert isinstance(opt.type, click.types.StringParamType)
    assert opt.default is UNSET


def test_batch_runs_with_valid_params(runner: CliRunner, tmp_path: pathlib.Path):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text(
        '{"channel": 0, "preproc": {}, "blob": {}}',
        encoding="utf-8",
    )

    mock_result = SimpleNamespace(
        num_blobs=42,
        num_frames=11,
        table_path=tmp_path / "blobs.csv",
        params_path=tmp_path / "params_output.json",
    )

    with patch(
        "apkit4d.cli.commands.batch.run_batch",
        return_value=mock_result,
    ) as mock_run:
        result = runner.invoke(
            cli,
            [
                "batch",
                str(czi),
                "--params",
                str(params),
                "--first-frame",
                "0",
                "--last-frame",
                "10",
                "--workers",
                "2",
                "--chunk",
                "5",
                "--format",
                "csv",
            ],
        )

    assert result.exit_code == 0, result.output
    assert "Batch processing completed." in result.output
    assert "Detected blobs: 42" in result.output

    mock_run.assert_called_once()

    kwargs = mock_run.call_args.kwargs
    assert kwargs["czi"] == czi
    assert kwargs["channel"] == 0
    assert kwargs["t0"] == 0
    assert kwargs["t1"] == 10
    assert kwargs["config"].workers == 2
    assert kwargs["config"].chunk_size == 5
    assert kwargs["config"].output_format == "csv"


@pytest.mark.parametrize(
    "arguments",
    [
        ["--workers", "0"],
        ["--chunk", "0"],
        ["--first-frame", "-1"],
        ["--last-frame", "-1"],
        ["--first-frame", "10", "--last-frame", "5"],
    ],
)
def test_batch_rejects_invalid_arguments(runner, tmp_path, arguments):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text("{}", encoding="utf-8")

    result = runner.invoke(
        cli,
        ["batch", str(czi), "--params", str(params), *arguments],
    )

    assert result.exit_code != 0


def test_batch_rejects_invalid_json(runner, tmp_path):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text("{invalid json", encoding="utf-8")

    result = runner.invoke(
        cli,
        ["batch", str(czi), "--params", str(params)],
    )

    assert result.exit_code != 0
    assert "Cannot load parameters" in result.output


@pytest.mark.parametrize(
    "content",
    [
        "[]",
        '"hello"',
        "123",
        "null",
    ],
)
def test_batch_rejects_non_object_json(runner, tmp_path, content):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text(content, encoding="utf-8")

    result = runner.invoke(
        cli,
        ["batch", str(czi), "--params", str(params)],
    )

    assert result.exit_code != 0
    assert "Parameters must be a JSON object." in result.output


def test_batch_loads_saved_params(runner, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    czi = tmp_path / "sample.czi"
    czi.touch()

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    (data_dir / "app_params.json").write_text(
        '{"sample": {"channel": 1, "t0": 5, "t1": 10}}',
        encoding="utf-8",
    )

    mock_result = SimpleNamespace(
        num_blobs=42,
        num_frames=6,
        table_path=tmp_path / "blobs.csv",
        params_path=tmp_path / "params_output.json",
    )

    with patch(
        "apkit4d.cli.commands.batch.run_batch",
        return_value=mock_result,
    ) as mock_run:
        result = runner.invoke(cli, ["batch", str(czi)])

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()

    kwargs = mock_run.call_args.kwargs
    assert kwargs["channel"] == 1
    assert kwargs["t0"] == 5
    assert kwargs["t1"] == 10
