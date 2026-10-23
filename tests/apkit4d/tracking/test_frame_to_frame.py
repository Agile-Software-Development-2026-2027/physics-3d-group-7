"""
Unit tests for frame-to-frame linking and Monte Carlo stability.
"""

import numpy as np
import pandas as pd

from apkit4d.core.models import TrackingConfig
from apkit4d.tracking.frame_to_frame import (
    POSITION_COLUMNS,
    compute_assignment_margins,
    evaluate_mc_stability,
    link_consecutive_frames,
)


def test_link_consecutive_frames_empty() -> None:
    """
    Verify handling of empty detections DataFrame.
    """
    cfg = TrackingConfig()
    df = pd.DataFrame(columns=["frame", *POSITION_COLUMNS])
    res = link_consecutive_frames(df, cfg)
    assert len(res.labels) == 0
    assert len(res.reliability) == 0


def test_link_consecutive_frames_single_frame() -> None:
    """
    Verify handling of a single frame dataset.
    """
    cfg = TrackingConfig()
    # POSITION_COLUMNS = ["z_um", "y_um", "x_um"]
    df = pd.DataFrame(
        {
            "frame": [0, 0],
            "z_um": [10.0, 20.0],
            "y_um": [10.0, 20.0],
            "x_um": [10.0, 20.0],
        }
    )
    res = link_consecutive_frames(df, cfg)
    assert len(res.labels) == 2
    assert res.labels[0] == 0
    assert res.labels[1] == 1


def test_link_consecutive_frames_two_frames_tracking() -> None:
    """
    Verify two straight-line tracks across two frames.
    """
    cfg = TrackingConfig(max_dist_um=15.0, mc_resamples=10)
    df = pd.DataFrame(
        {
            "frame": [0, 0, 1, 1],
            "z_um": [10.0, 50.0, 12.0, 52.0],
            "y_um": [0.0, 0.0, 0.0, 0.0],
            "x_um": [0.0, 0.0, 0.0, 0.0],
        }
    )
    res = link_consecutive_frames(df, cfg)
    # Frame 0 particle 0 (z=10) should link to frame 1 detection (z=12)
    # Frame 0 particle 1 (z=50) should link to frame 1 detection (z=52)
    assert res.labels[0] == res.labels[2]
    assert res.labels[1] == res.labels[3]
    assert np.isfinite(res.reliability[2])
    assert np.isfinite(res.reliability[3])


def test_evaluate_mc_stability_empty() -> None:
    """
    Verify evaluate_mc_stability handles zero resamples or empty pairs.
    """
    pred = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    cur = np.array([[0.0, 0.0, 0.0]], dtype=np.float32)
    rows = np.array([0], dtype=np.int32)
    cols = np.array([0], dtype=np.int32)
    pairs = np.array([[0, 0]], dtype=np.int32)
    sigma = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    rng = np.random.default_rng(0)

    res = evaluate_mc_stability(
        predicted_positions=pred,
        current_positions=cur,
        candidate_rows=rows,
        candidate_cols=cols,
        matched_pairs=pairs,
        sigma=sigma,
        num_resamples=0,
        rng=rng,
    )
    assert res == {}

    empty_pairs = np.empty((0, 2), dtype=np.int32)
    res2 = evaluate_mc_stability(
        predicted_positions=pred,
        current_positions=cur,
        candidate_rows=rows,
        candidate_cols=cols,
        matched_pairs=empty_pairs,
        sigma=sigma,
        num_resamples=10,
        rng=rng,
    )
    assert res2 == {}


def test_compute_assignment_margins_empty() -> None:
    """
    Verify compute_assignment_margins handles empty matches.
    """
    pred = np.empty((0, 3), dtype=np.float32)
    cur = np.empty((0, 3), dtype=np.float32)
    rows = np.empty(0, dtype=np.int32)
    cols = np.empty(0, dtype=np.int32)
    pairs = np.empty((0, 2), dtype=np.int32)
    sigma = np.array([1.0, 1.0, 1.0], dtype=np.float32)

    margins, cand_counts = compute_assignment_margins(
        predicted_positions=pred,
        current_positions=cur,
        candidate_rows=rows,
        candidate_cols=cols,
        matched_pairs=pairs,
        sigma=sigma,
    )
    assert margins == {}
    assert cand_counts == {}


# I know my comments of the function are very creative and are not the same as teh title of the function
