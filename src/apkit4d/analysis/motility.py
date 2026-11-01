"""Biophysical motility analysis for reconstructed cell trajectories.

This module provides analytics such as the direction autocorrelation function (ACF)
to evaluate helical swimming dynamics and path persistence.
"""

from typing import Final

import numpy as np
import pandas as pd

COORDINATE_COLUMNS: Final[list[str]] = ["z_um", "y_um", "x_um"]


def compute_direction_acf(
    tracks: pd.DataFrame,
    max_lag: int = 15,
    min_points: int = 20,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute direction autocorrelation function <cos θ(theta)> across time lags on long tracks.

    Serves two purposes at once: random connections crush it to zero, while Chlamydomonas'
    helical swimming (~2 Hz rotation) makes it oscillate, with minima at half-turn and
    maxima at full turn. In the file at 10 vol/s, the measured period is 4 frames ≈ 0.4 s.

    Args:
        tracks: DataFrame of reconstructed trajectories. Must contain 'track_id' and
            coordinate columns ['z_um', 'y_um', 'x_um'].
        max_lag: Maximum frame lag to evaluate (default 15).
        min_points: Minimum number of detection points required for a trajectory to be
            included in autocorrelation calculations (default 20).

    Returns:
        Tuple of (lags, acf_values) as 1D numpy arrays. If no trajectories meet the
        `min_points` threshold or tracks is empty, returns two empty arrays.

    RefactorNote:
        Equivalent of `direction_acf` from legacy
    """
    if tracks.empty or "track_id" not in tracks.columns or max_lag < 1:
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64)

    lag_products: dict[int, list[np.ndarray]] = {lag: [] for lag in range(1, max_lag + 1)}

    for _, group in tracks.groupby("track_id"):
        if len(group) < min_points:
            continue

        coords = group[COORDINATE_COLUMNS].to_numpy()
        displacements = np.diff(coords, axis=0)
        norms = np.linalg.norm(displacements, axis=1, keepdims=True)
        unit_vectors = displacements / np.maximum(norms, 1e-9)

        num_steps = len(unit_vectors)
        for lag in range(1, max_lag + 1):
            if num_steps > lag:
                cos_theta = (unit_vectors[:-lag] * unit_vectors[lag:]).sum(axis=1)
                lag_products[lag].append(cos_theta)

    valid_lags = [lag for lag in lag_products if len(lag_products[lag]) > 0]
    if not valid_lags:
        return np.array([], dtype=np.int64), np.array([], dtype=np.float64)

    lags_arr = np.array(valid_lags, dtype=np.int64)
    acf_arr = np.array(
        [float(np.concatenate(lag_products[lag]).mean()) for lag in valid_lags],
        dtype=np.float64,
    )

    return lags_arr, acf_arr
