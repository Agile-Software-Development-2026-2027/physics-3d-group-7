"""The export names the tables it saved in its json, so that the results can be opened again."""

import json
from pathlib import Path

import pandas as pd
import pytest

from apkit4d.batching.export import save_batch_results, save_tracks
from apkit4d.core.models import TrackingConfig
from apkit4d.io.table import read_table

DETECTIONS = pd.DataFrame({"frame": [0, 1, 2, 3], "x_um": [1.0, 2.0, 3.0, 4.0]})
TRACKS = DETECTIONS.assign(track_id=[0, 0, 1, 1])


def export(folder, detections=DETECTIONS, first=1, last=2, fmt="csv", **tracking):
    metadata = {"czi": str(folder / "sample.czi"), "channel": 0, "t0": 0, "t1": 3, "blob": {}}
    result = save_batch_results(detections, metadata, folder, fmt, first, last, lambda *_: None, **tracking)
    return result, json.loads(result.params_path.read_text())


def test_tracks_are_saved_for_the_same_frames_as_the_blobs(tmp_path):
    result, saved = export(tmp_path, tracks=TRACKS, tracking_config=TrackingConfig(min_len=2))

    assert result.params_path == tmp_path / "sample_blobs_params.json"
    assert saved["table"] == "sample_blobs.csv"
    assert saved["tracks_table"] == "sample_tracks.csv"
    assert saved["tracking"]["min_len"] == 2
    assert read_table(tmp_path / "sample_tracks.csv")["frame"].tolist() == [1, 2]


def test_without_tracks_the_json_names_no_tracks_table(tmp_path):
    _, saved = export(tmp_path)

    assert saved["table"] == "sample_blobs.csv"
    assert saved["tracks_table"] is None
    assert "tracking" not in saved


def test_an_export_without_blobs_names_no_table(tmp_path):
    result, saved = export(tmp_path, detections=DETECTIONS.iloc[:0])

    assert saved["table"] is None
    assert not result.table_path.exists()


def test_a_failed_tracks_table_is_not_left_behind(tmp_path, monkeypatch):
    def write_half(df, path):
        Path(path).write_text("frame\n")
        raise OSError("disk full")

    monkeypatch.setattr("apkit4d.batching.export.write_table", write_half)
    with pytest.raises(OSError, match="disk full"):
        export(tmp_path, fmt="parquet", tracks=TRACKS)
    assert not (tmp_path / "sample_tracks.parquet").exists()


def test_tracks_linked_later_are_saved_next_to_the_blobs_and_named_in_the_json(tmp_path):
    result, _ = export(tmp_path)

    tracks_path = save_tracks(result.params_path, TRACKS, TrackingConfig(min_len=3), "csv")

    assert tracks_path == tmp_path / "sample_tracks.csv"
    saved = json.loads(result.params_path.read_text())
    assert saved["tracks_table"] == "sample_tracks.csv"
    assert saved["tracking"]["min_len"] == 3
    assert read_table(tracks_path)["track_id"].tolist() == [0, 0, 1, 1]
    with pytest.raises(ValueError, match="xlsx"):
        save_tracks(result.params_path, TRACKS, TrackingConfig(), "xlsx")
