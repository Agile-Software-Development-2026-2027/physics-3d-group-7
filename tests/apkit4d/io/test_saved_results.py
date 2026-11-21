"""Saved results must come back as they were exported, also the ones written by older exports."""

import json
import logging

import pandas as pd
import pytest

from apkit4d.batching.export import save_batch_results
from apkit4d.core.models import TrackingConfig
from apkit4d.detection.preprocessing import BgMode, PreprocParams
from apkit4d.io.saved_results import read_saved_results
from apkit4d.io.table import write_table

DETECTIONS = pd.DataFrame(
    {
        "frame": [0, 1, 2, 3],
        "x_um": [1.0, 2.0, 3.0, 4.0],
        "y_um": [5.0, 6.0, 7.0, 8.0],
        "z_um": [9.0, 9.5, 10.0, 10.5],
        "response": [0.4, 0.5, 0.6, 0.7],
    }
)
TRACKS = DETECTIONS.assign(track_id=[0, 0, 1, 1])


def export(folder, recording, *, detections=DETECTIONS, tracks=None, config=None, fmt="parquet"):
    """Save results of `recording` in `folder` like the Batch stage does, and return the json path."""
    metadata = {
        "czi": str(recording),
        "channel": 0,
        "t0": 0,
        "t1": 3,
        "info": {"dt_s": 0.5},
        "preproc": PreprocParams(bg_mode=BgMode.WIDE_GAUSSIAN, gamma_correction_to_apply=0.8).to_dict(),
        "blob": {"threshold": 0.25},
    }
    result = save_batch_results(
        detections, metadata, folder, fmt, 0, 3, lambda *_: None, tracks=tracks, tracking_config=config
    )
    return result.params_path


@pytest.fixture
def recording(tmp_path):
    path = tmp_path / "sample.czi"
    path.write_bytes(b"")
    return path


@pytest.mark.parametrize("fmt", ["parquet", "csv"])
def test_exported_results_come_back_with_their_recording(tmp_path, recording, fmt):
    params = export(tmp_path / "out", recording, tracks=TRACKS, config=TrackingConfig(min_len=2), fmt=fmt)

    saved = read_saved_results(params)
    assert saved.recording == recording.resolve()
    assert saved.recording_name == "sample.czi"
    assert saved.channel == 0

    session = saved.load_session()
    assert session.blobs is not None
    assert session.blobs["frame"].tolist() == [0, 1, 2, 3]
    assert session.blobs["response"].tolist() == pytest.approx([0.4, 0.5, 0.6, 0.7])
    assert session.tracking is not None
    assert session.tracking.tracks["track_id"].tolist() == [0, 0, 1, 1]
    assert session.blob_params is not None and session.blob_params.threshold == 0.25
    assert session.preproc_params is not None
    assert session.preproc_params.bg_mode == BgMode.WIDE_GAUSSIAN
    assert session.preproc_params.gamma_correction_to_apply == 0.8
    assert session.tracking_config == TrackingConfig(min_len=2)


def test_results_without_tracks_ignore_old_tracks_in_the_folder(tmp_path, recording):
    params = export(tmp_path, recording)
    write_table(TRACKS, tmp_path / "sample_tracks.parquet")  # left there by an earlier export

    session = read_saved_results(params).load_session()
    assert session.tracking is None
    assert session.tracking_config is None


def test_an_empty_export_comes_back_without_blobs(tmp_path, recording):
    params = export(tmp_path, recording, detections=DETECTIONS.iloc[:0])

    session = read_saved_results(params).load_session()
    assert session.blobs is not None and session.blobs.empty
    assert {"frame", "x_um", "y_um", "z_um"} <= set(session.blobs.columns)


def test_a_missing_table_is_reported(tmp_path, recording):
    params = export(tmp_path, recording, tracks=TRACKS)
    (tmp_path / "sample_tracks.parquet").unlink()

    with pytest.raises(FileNotFoundError, match="sample_tracks.parquet"):
        read_saved_results(params).load_session()


def test_results_of_the_old_apkit4d_are_read(tmp_path, caplog):
    # the old ApKit4D saved in a subfolder of the recordings, with a path relative to where it ran
    (tmp_path / "Experiment.czi").write_bytes(b"")
    out = tmp_path / "out"
    out.mkdir()
    old = {
        "czi": "..\\data\\Experiment.czi",
        "channel": 0,
        "preproc": {"bg_mode": "nessuno", "clip_lo": 1.0},
        "blob": {"threshold": 0.1, "split": 1.0},
        "n_blobs": 4,
        "formato": "csv",
    }
    (out / "Experiment_blobs_params.json").write_text(json.dumps(old))
    write_table(DETECTIONS, out / "Experiment_blobs.csv")
    write_table(TRACKS.rename(columns={"track_id": "particle"}), out / "Experiment_tracks.parquet")

    saved = read_saved_results(out / "Experiment_blobs_params.json")
    assert saved.recording == (tmp_path / "Experiment.czi").resolve()

    with caplog.at_level(logging.WARNING):
        session = saved.load_session()
    assert session.blobs is not None and len(session.blobs) == 4
    assert session.tracking is not None
    assert session.tracking.tracks["track_id"].tolist() == [0, 0, 1, 1]
    assert session.blob_params is not None and session.blob_params.threshold == 0.1
    assert session.preproc_params is None  # other names and Italian values
    assert "preproc" in caplog.text


def test_old_results_without_their_blobs_table_are_reported(tmp_path):
    # a renamed json of an old export: its tables can no longer be found by name
    params = tmp_path / "renamed.json"
    params.write_text(json.dumps({"czi": "sample.czi", "n_blobs": 4}))
    write_table(DETECTIONS, tmp_path / "sample_blobs.parquet")

    with pytest.raises(FileNotFoundError, match="blobs table of renamed.json"):
        read_saved_results(params).load_session()


@pytest.mark.parametrize("written", ["/home/someone/data/sample.czi", "D:\\data\\sample.czi"])
def test_the_recording_is_looked_for_next_to_the_results(tmp_path, written):
    # results saved on another computer, then copied here with their recording
    export(tmp_path, tmp_path / "sample.czi")
    params = tmp_path / "sample_blobs_params.json"
    metadata = json.loads(params.read_text())
    params.write_text(json.dumps({**metadata, "czi": written}))

    assert read_saved_results(params).recording is None
    (tmp_path / "sample.czi").write_bytes(b"")
    assert read_saved_results(params).recording == (tmp_path / "sample.czi").resolve()


@pytest.mark.parametrize("content", ["not json", "[1, 2]", '{"channel": 0}'])
def test_files_that_are_not_saved_results_are_rejected(tmp_path, content):
    params = tmp_path / "other_blobs_params.json"
    params.write_text(content)

    with pytest.raises(ValueError, match="other_blobs_params.json"):
        read_saved_results(params)
