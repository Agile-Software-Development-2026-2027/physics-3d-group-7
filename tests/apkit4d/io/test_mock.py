"""Unit tests for the synthetic mock microscopy source and trajectories."""

import numpy as np
import pytest

from apkit4d.io.mock import (
    MOCK_TRACK_COLUMNS,
    MockConfig,
    MockFrameSource,
    create_mock_source,
    generate_mock_tracks,
)


def test_generate_mock_tracks_schema_and_sorting() -> None:
    cfg = MockConfig(n_t=60, n_z=12, n_y=64, n_x=64, seed=7)
    tracks, profiles = generate_mock_tracks(cfg)

    assert list(tracks.columns) == MOCK_TRACK_COLUMNS
    assert len(tracks) > 0
    assert set(profiles.keys()) == set(tracks["track_id"].unique().tolist())

    # Must be sorted by (track_id, frame) matching ParticleLinker contract
    sorted_tracks = tracks.sort_values(["track_id", "frame"]).reset_index(drop=True)
    assert tracks.equals(sorted_tracks)

    # Labels within each frame must be 1..K without duplicates
    for _, frame_df in tracks.groupby("frame"):
        labels = frame_df["label"].to_numpy()
        assert np.array_equal(np.sort(labels), np.arange(1, len(frame_df) + 1))


def test_generate_mock_tracks_motion_variety_and_bounds() -> None:
    cfg = MockConfig()
    tracks, profiles = generate_mock_tracks(cfg)

    profile_values = set(profiles.values())
    assert "tight_helix" in profile_values
    assert "wide_helix" in profile_values
    assert "linear" in profile_values
    assert "smooth_curve" in profile_values
    assert "gapped_transient" in profile_values

    x_limit = (cfg.n_x - 1) * cfg.px_size_x
    y_limit = (cfg.n_y - 1) * cfg.px_size_y
    z_limit = (cfg.n_z - 1) * cfg.px_size_z

    assert tracks["x_um"].min() >= 0.0
    assert tracks["x_um"].max() <= x_limit
    assert tracks["y_um"].min() >= 0.0
    assert tracks["y_um"].max() <= y_limit
    assert tracks["z_um"].min() >= 0.0
    assert tracks["z_um"].max() <= z_limit

    # Step speeds must stay physically bounded below TrackingConfig default ceiling (250 um/s)
    for _, grp in tracks.groupby("track_id"):
        coords = grp[["x_um", "y_um", "z_um"]].to_numpy(dtype=np.float64)
        dt = np.diff(grp["t_s"].to_numpy(dtype=np.float64))
        disp = np.linalg.norm(np.diff(coords, axis=0), axis=1)
        speeds = disp / dt
        assert np.all(np.isfinite(speeds))
        assert np.all(speeds < 250.0)


def test_generate_mock_tracks_rejects_too_few_frames() -> None:
    with pytest.raises(ValueError, match="n_t must be >= 2"):
        generate_mock_tracks(MockConfig(n_t=1))


def test_mock_frame_source_reads_aligned_blobs_and_summary() -> None:
    cfg = MockConfig(n_t=20, n_z=10, n_y=48, n_x=48, seed=99)
    source = create_mock_source(cfg)

    assert isinstance(source, MockFrameSource)
    assert source.info.n_t == 20
    assert source.info.voxel == (cfg.px_size_z, cfg.px_size_y, cfg.px_size_x)
    assert source.info.dt_source == "mock"

    vol0 = source.read(0)
    assert vol0.shape == (cfg.n_z, cfg.n_y, cfg.n_x)
    assert vol0.dtype == np.uint16
    assert np.array_equal(vol0, source.read(0))

    # Active frame-0 blobs must produce clear peaks above background at their voxel centers
    frame0_blobs = source.tracks[source.tracks["frame"] == 0]
    assert len(frame0_blobs) > 0
    for row in frame0_blobs.itertuples(index=False):
        zi = round(float(row.z))
        yi = round(float(row.y))
        xi = round(float(row.x))
        assert vol0[zi, yi, xi] > MockFrameSource.BACKGROUND_LEVEL + 500.0

    # Returning defensive copy prevents mutation of internal state
    tracks_copy = source.tracks
    tracks_copy.loc[:, "x_um"] = -999.0
    assert source.tracks["x_um"].min() >= 0.0

    summary = source.summary()
    assert summary["n_t"] == cfg.n_t
    assert summary["shape_zyx"] == (cfg.n_z, cfg.n_y, cfg.n_x)
    assert summary["n_tracks"] == len(source.motion_profiles)
    assert summary["n_detections"] == len(source.tracks)
    assert 0.0 < summary["speed_um_s"]["mean"] <= summary["speed_um_s"]["max"]


def test_mock_frame_source_bounds_and_close_guards() -> None:
    source = create_mock_source(MockConfig(n_t=5, n_z=6, n_y=24, n_x=24))

    with pytest.raises(IndexError):
        source.read(-1)
    with pytest.raises(IndexError):
        source.read(5)

    source.close()
    with pytest.raises(RuntimeError, match="closed"):
        source.read(0)
