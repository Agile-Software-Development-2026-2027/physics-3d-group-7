import json
import pathlib
from types import SimpleNamespace
from unittest.mock import patch

import click
import pandas as pd
import pytest
from click._utils import UNSET
from click.testing import CliRunner

from apkit4d.batching.export import save_batch_results
from apkit4d.cli import cli
from apkit4d.core.roi import RegionOfInterest
from apkit4d.io.table import read_table
from tests.apkit4d.cli.helper import get_argument, get_option, is_param_defined

PIPELINE = cli.commands["pipeline"]


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def test_apkit4d_pipeline_is_defined(runner: CliRunner):
    result = runner.invoke(cli, ["pipeline", "--help"])
    assert result.exit_code == 0


@pytest.mark.parametrize(
    "param",
    [
        "file",
        "--input-dir",
        "--params",
        "--first-frame",
        "--last-frame",
        "--only",
        "--out",
        "--workers",
        "--chunk",
        "--format",
    ],
)
def test_apkit4d_pipeline_has_params_defined(param: str):
    assert is_param_defined(PIPELINE, param)


def test_file_accepts_multiple_existing_paths():
    arg = get_argument(PIPELINE, "file")
    assert not arg.required
    assert arg.nargs == -1
    assert isinstance(arg.type, click.Path)
    assert arg.type.type is pathlib.Path
    assert arg.type.exists
    assert not arg.type.dir_okay


def test_first_frame_is_an_option_and_an_int():
    opt = get_option(PIPELINE, "--first-frame")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default is UNSET


def test_last_frame_is_an_option_and_an_int():
    opt = get_option(PIPELINE, "--last-frame")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default is UNSET


def test_out_is_an_option_and_a_dir():
    opt = get_option(PIPELINE, "--out")
    assert isinstance(opt.type, click.Path)
    assert opt.type.type is pathlib.Path
    assert opt.type.dir_okay
    assert not opt.type.file_okay
    assert opt.default is UNSET


def test_workers_is_an_option_and_an_int_with_default_16():
    opt = get_option(PIPELINE, "--workers")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default == 16


def test_chunk_is_an_option_and_an_int_with_default_10():
    opt = get_option(PIPELINE, "--chunk")
    assert isinstance(opt.type, click.types.IntParamType)
    assert opt.default == 10


def test_format_is_an_option_and_an_choice_with_default_parquet():
    opt = get_option(PIPELINE, "--format")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["parquet", "csv"]
    assert opt.default == "parquet"


def test_params_is_an_option_and_a_string():
    opt = get_option(PIPELINE, "--params")
    assert isinstance(opt.type, click.types.StringParamType)
    assert opt.default is UNSET


def test_detection_runs_with_valid_params(runner: CliRunner, tmp_path: pathlib.Path):
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
        "apkit4d.cli.commands.pipeline.run_batch",
        return_value=mock_result,
    ) as mock_run:
        result = runner.invoke(
            cli,
            [
                "pipeline",
                str(czi),
                "--only",
                "detection",
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
    assert "Detection completed." in result.output
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
def test_pipeline_rejects_invalid_arguments(runner, tmp_path, arguments):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text("{}", encoding="utf-8")

    result = runner.invoke(
        cli,
        ["pipeline", str(czi), "--params", str(params), *arguments],
    )

    assert result.exit_code != 0


def test_pipeline_rejects_invalid_json(runner, tmp_path):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text("{invalid json", encoding="utf-8")

    result = runner.invoke(
        cli,
        ["pipeline", str(czi), "--params", str(params)],
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
def test_pipeline_rejects_non_object_json(runner, tmp_path, content):
    czi = tmp_path / "sample.czi"
    czi.touch()

    params = tmp_path / "params.json"
    params.write_text(content, encoding="utf-8")

    result = runner.invoke(
        cli,
        ["pipeline", str(czi), "--params", str(params)],
    )

    assert result.exit_code != 0
    assert "Parameters must be a JSON object." in result.output


def test_pipeline_loads_saved_params(runner, tmp_path, monkeypatch):
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
        "apkit4d.cli.commands.pipeline.run_batch",
        return_value=mock_result,
    ) as mock_run:
        result = runner.invoke(cli, ["pipeline", str(czi), "--only", "detection"])

    assert result.exit_code == 0, result.output
    mock_run.assert_called_once()

    kwargs = mock_run.call_args.kwargs
    assert kwargs["channel"] == 1
    assert kwargs["t0"] == 5
    assert kwargs["t1"] == 10


def test_only_is_an_optional_choice():
    opt = get_option(PIPELINE, "--only")
    assert isinstance(opt.type, click.Choice)
    assert list(opt.type.choices) == ["detection", "linking"]
    assert not opt.required
    assert opt.default is None


# two blobs moving slowly for three frames: two tracks
BLOBS = pd.DataFrame(
    {
        "frame": [0, 1, 2, 0, 1, 2],
        "x_um": [1.0, 1.5, 2.0, 30.0, 30.5, 31.0],
        "y_um": [1.0, 1.0, 1.0, 30.0, 30.0, 30.0],
        "z_um": [1.0, 1.0, 1.0, 1.0, 1.0, 1.0],
    }
)


def save_results(folder: pathlib.Path, recording: pathlib.Path):
    """Blobs of `recording` saved like the Batch export of the app."""
    metadata = {"czi": str(recording), "channel": 0, "t0": 0, "t1": 2, "info": {"dt_s": 0.5}, "preproc": {}}
    return save_batch_results(BLOBS, metadata, folder, "parquet", 0, 2, lambda *_: None)


def write_params(folder: pathlib.Path, params: dict) -> pathlib.Path:
    path = folder / "params.json"
    path.write_text(json.dumps(params), encoding="utf-8")
    return path


def test_detection_is_followed_by_linking_next_to_the_results(runner, tmp_path):
    czi = tmp_path / "sample.czi"
    czi.touch()
    detected = save_results(tmp_path, czi)
    params = write_params(tmp_path, {"tracking": {"min_len": 2}})

    with patch("apkit4d.cli.commands.pipeline.run_batch", return_value=detected) as mock_run:
        result = runner.invoke(cli, ["pipeline", str(czi), "--params", str(params)])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["out_dir"] == tmp_path  # the folder of the recording by default
    saved = json.loads(detected.params_path.read_text())
    assert saved["tracks_table"] == "sample_tracks.parquet"
    assert saved["tracking"]["min_len"] == 2
    assert read_table(tmp_path / "sample_tracks.parquet")["track_id"].nunique() == 2
    assert f"apkit4d gui {detected.params_path}" in result.output


def test_saved_results_are_linked_again_with_new_parameters(runner, tmp_path):
    czi = tmp_path / "sample.czi"
    czi.touch()
    params_path = save_results(tmp_path, czi).params_path
    params = write_params(tmp_path, {"tracking": {"min_len": 4}})

    result = runner.invoke(cli, ["pipeline", str(params_path), "--params", str(params), "--format", "csv"])

    assert result.exit_code == 0, result.output
    assert "Linking completed." in result.output
    saved = json.loads(params_path.read_text())
    assert saved["tracks_table"] == "sample_tracks.csv"
    assert saved["tracking"]["min_len"] == 4
    assert read_table(tmp_path / "sample_tracks.csv").empty  # no blob lasts 4 frames


def test_the_roi_of_the_parameters_goes_to_the_detection(runner, tmp_path):
    czi = tmp_path / "sample.czi"
    czi.touch()
    roi = RegionOfInterest(x_min=0.0, x_max=5.0, y_min=0.0, y_max=5.0, z_min=0.0, z_max=2.0)
    params = write_params(tmp_path, {"roi": roi.to_dict()})
    detected = SimpleNamespace(num_blobs=0, num_frames=1, table_path=None, params_path=None)

    with patch("apkit4d.cli.commands.pipeline.run_batch", return_value=detected) as mock_run:
        result = runner.invoke(cli, ["pipeline", str(czi), "--params", str(params), "--only", "detection"])

    assert result.exit_code == 0, result.output
    assert mock_run.call_args.kwargs["roi"] == roi


@pytest.mark.parametrize(("suffix", "only"), [(".json", "detection"), (".czi", "linking")])
def test_a_step_that_cannot_run_on_the_file_is_refused(runner, tmp_path, suffix, only):
    file = tmp_path / f"sample{suffix}"
    file.write_text("{}", encoding="utf-8")

    result = runner.invoke(cli, ["pipeline", str(file), "--only", only])

    assert result.exit_code == 2


@pytest.mark.parametrize(
    ("params", "message"),
    [
        ({"blob": {"threshold": 99}}, "Invalid parameters"),
        ({"tracking": {"max_dist_um": -1}}, "Invalid tracking parameters"),
    ],
)
def test_invalid_parameters_are_reported(runner, tmp_path, params, message):
    czi = tmp_path / "sample.czi"
    czi.touch()
    detected = save_results(tmp_path, czi)

    with patch("apkit4d.cli.commands.pipeline.run_batch", return_value=detected):
        result = runner.invoke(cli, ["pipeline", str(czi), "--params", str(write_params(tmp_path, params))])

    assert result.exit_code == 1
    assert message in result.output


def test_unreadable_saved_results_are_reported(runner, tmp_path):
    results = tmp_path / "sample_blobs_params.json"
    results.write_text("{}", encoding="utf-8")

    result = runner.invoke(cli, ["pipeline", str(results)])

    assert result.exit_code == 1
    assert "Cannot read the saved results" in result.output


def test_multiple_recordings_use_shared_parameters_and_write_separate_results(runner, tmp_path):
    first = tmp_path / "source.czi"
    second = tmp_path / "other" / first.name
    second.parent.mkdir()
    first.touch()
    second.touch()
    output = tmp_path / "exports"
    params = write_params(tmp_path, {"blob": {"threshold": 0.2}, "tracking": {"min_len": 2}})

    def detect(**kwargs):
        return save_results(kwargs["out_dir"], kwargs["czi"])

    with patch("apkit4d.cli.commands.pipeline.run_batch", side_effect=detect) as mock_run:
        result = runner.invoke(
            cli, ["pipeline", str(first), str(second), "--params", str(params), "--out", str(output)]
        )

    assert result.exit_code == 0, result.output
    calls = [call.kwargs for call in mock_run.call_args_list]
    assert [call["czi"] for call in calls] == [first, second]
    assert all(call["blob_params"].threshold == 0.2 for call in calls)
    exports = list(output.glob("*/*_blobs_params.json"))
    assert len(exports) == 2
    saved_recordings = set()
    for path in exports:
        saved = json.loads(path.read_text())
        saved_recordings.add(pathlib.Path(saved["czi"]))
        assert saved["tracking"]["min_len"] == 2
        assert (path.parent / saved["tracks_table"]).is_file()
    assert saved_recordings == {first, second}


def test_multiple_recordings_continue_after_a_failure(runner, tmp_path):
    first = tmp_path / "broken.czi"
    second = tmp_path / "valid.czi"
    first.touch()
    second.touch()
    detected = save_results(tmp_path, second)

    with patch("apkit4d.cli.commands.pipeline.run_batch", side_effect=[ValueError("Invalid CZI"), detected]):
        result = runner.invoke(cli, ["pipeline", str(first), str(second), "--only", "detection"])

    assert result.exit_code == 1
    assert f"Failed to process {first}: Invalid CZI" in result.output
    assert "Detection completed." in result.output
    assert "Processed 1 of 2 recordings." in result.output


@pytest.mark.parametrize("names", [("only.czi",), ("z.czi", "a.CZI")])
def test_input_directory_processes_czi_files_in_filename_order(runner, tmp_path, names):
    for name in names:
        (tmp_path / name).touch()
    (tmp_path / "notes.txt").touch()
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / "ignored.czi").touch()
    output = tmp_path / "exports"
    detected = SimpleNamespace(num_blobs=0, num_frames=1, table_path=None, params_path=None)

    with patch("apkit4d.cli.commands.pipeline.run_batch", return_value=detected) as mock_run:
        result = runner.invoke(
            cli, ["pipeline", "--input-dir", str(tmp_path), "--only", "detection", "--out", str(output)]
        )

    assert result.exit_code == 0, result.output
    calls = [call.kwargs for call in mock_run.call_args_list]
    assert [call["czi"].name for call in calls] == sorted(names)
    assert all(call["out_dir"].parent == output for call in calls)


def test_input_directory_reports_no_czi_recordings(runner, tmp_path):
    result = runner.invoke(cli, ["pipeline", "--input-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "No CZI recordings found" in result.output


def test_input_directory_and_file_arguments_are_mutually_exclusive(runner, tmp_path):
    recording = tmp_path / "sample.czi"
    recording.touch()
    result = runner.invoke(cli, ["pipeline", str(recording), "--input-dir", str(tmp_path)])
    assert result.exit_code == 2
    assert "Specify FILE arguments or --input-dir" in result.output


def test_pipeline_requires_an_input(runner):
    result = runner.invoke(cli, ["pipeline"])
    assert result.exit_code == 2
    assert "Specify at least one FILE or use --input-dir" in result.output
