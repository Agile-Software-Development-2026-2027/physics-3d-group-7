"""
Quantitative trajectory metrics calculation for particle tracking.

This module computes per-track metrics like displacement, path length,
median velocity/step size, turn angle, connection reliability and number of gaps.
"""

from typing import Final

import numpy as np
import pandas as pd

COORDINATE_COLUMNS: Final[list[str]] = ["z_um", "y_um", "x_um"]

STATS_COLUMNS: Final[list[str]] = [
    "track_id",
    "n_points",
    "span_frames",
    "mean_reliability",
    "min_reliability",
    "frac_uncertain_steps",
    "min_margin_sigma",
    "frac_contested_steps",
    "n_gaps",
    "duration_s",
    "net_displacement_um",
    "path_length_um",
    "median_step_um",
    "median_turn_deg",
    "frac_turn_gt_120",
]


def compute_track_statistics(tracks: pd.DataFrame) -> pd.DataFrame:
    """
    Compute per-trajectory summary statistics.

    Args:
        tracks: DataFrame of tracked particle positions. Must contain 'track_id', 'frame',
            and coordinate columns ['z_um', 'y_um', 'x_um']. May optionally include
            't_s', 'reliability', 'margin_sigma', and 'candidate_count'.

    Returns:
        DataFrame with one row per trajectory containing summary metrics.

    RefactorNote:
        Equivalent of `track_stats` from legacy
    """
    if tracks.empty or "track_id" not in tracks.columns:
        return pd.DataFrame(columns=STATS_COLUMNS)

    rows: list[dict[str, object]] = []

    for track_id, group in tracks.groupby("track_id"):
        xyz = group[COORDINATE_COLUMNS].to_numpy()
        frames = group["frame"].to_numpy()

        diffs = np.diff(xyz, axis=0)
        frame_diffs = np.diff(frames)
        steps = np.linalg.norm(diffs, axis=1)

        dt_s = group["t_s"].to_numpy() if "t_s" in group else None
        duration_s = (
            float(dt_s[-1] - dt_s[0])
            if dt_s is not None and len(dt_s) > 0 and np.isfinite(dt_s).all()
            else np.nan
        )

        angles = np.array([], dtype=np.float64)
        if len(diffs) >= 2:
            step_norms = np.linalg.norm(diffs, axis=1, keepdims=True)
            unit_vectors = diffs / np.maximum(step_norms, 1e-9)
            cosines = np.clip((unit_vectors[:-1] * unit_vectors[1:]).sum(axis=1), -1.0, 1.0)
            angles = np.degrees(np.arccos(cosines))

        reliability = (
            group["reliability"].to_numpy()
            if "reliability" in group
            else np.array([np.nan], dtype=np.float64)
        )
        finite_reliability = reliability[np.isfinite(reliability)]

        margin = (
            group["margin_sigma"].to_numpy()
            if "margin_sigma" in group
            else np.array([np.nan], dtype=np.float64)
        )
        finite_margin = margin[np.isfinite(margin)]

        candidate_counts = (
            group["candidate_count"].to_numpy()
            if "candidate_count" in group
            else np.array([0], dtype=np.int64)
        )

        net_disp = float(np.linalg.norm(xyz[-1] - xyz[0])) if len(xyz) > 0 else 0.0

        rows.append(
            {
                "track_id": track_id,
                "n_points": len(group),
                "span_frames": int(frames[-1] - frames[0] + 1) if len(frames) > 0 else 0,
                "mean_reliability": (
                    float(np.mean(finite_reliability)) if len(finite_reliability) else np.nan
                ),
                "min_reliability": (float(np.min(finite_reliability)) if len(finite_reliability) else np.nan),
                "frac_uncertain_steps": (
                    float((finite_reliability < 0.5).mean()) if len(finite_reliability) else np.nan
                ),
                "min_margin_sigma": (float(np.min(finite_margin)) if len(finite_margin) else np.inf),
                "frac_contested_steps": (
                    float((candidate_counts > 1).mean()) if len(candidate_counts) else np.nan
                ),
                "n_gaps": int((frame_diffs > 1).sum()),
                "duration_s": duration_s,
                "net_displacement_um": net_disp,
                "path_length_um": float(steps.sum()),
                "median_step_um": float(np.median(steps)) if len(steps) else np.nan,
                "median_turn_deg": float(np.median(angles)) if len(angles) else np.nan,
                "frac_turn_gt_120": float((angles > 120.0).mean()) if len(angles) else np.nan,
            }
        )

    return pd.DataFrame(rows)
