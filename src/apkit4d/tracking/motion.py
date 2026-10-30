"""
Kinematic motion modeling and prediction utilities for trajectory tracking.

This module provides functions for physical search gate calculation, exponential
moving average (EMA) position and velocity updates, and adaptive uncertainty
variance estimation based on empirical prediction residuals.
"""

import numpy as np
from numpy.typing import NDArray

MAD_SCALE_FACTOR: float = 1.4826
MIN_SIGMA_VALUE: float = 1e-3


def compute_search_gate(dt_s: float, max_speed_um_s: float = 250.0) -> float:
    """
    Calculate the physical search gate radius from time interval and max speed.

    Args:
        dt_s: Sampling time interval between consecutive frames in seconds.
        max_speed_um_s: Expected upper bound on physical swimming speed (µm/s).

    Returns:
        Search gate radius in micrometers (µm).

    RefactorNote:
        This is teh same as `gate_from_dt` but with some Error checking.
    """
    if dt_s <= 0.0:
        raise ValueError(f"Time interval dt_s must be positive, got {dt_s}")
    if max_speed_um_s <= 0.0:
        raise ValueError(f"Max speed max_speed_um_s must be positive, got {max_speed_um_s}")
    return float(max_speed_um_s * dt_s)


def predict_positions_ema(
    positions: NDArray[np.float32], velocities: NDArray[np.float32]
) -> NDArray[np.float32]:
    """
    Predict next positions given current positions and estimated velocities.

    Args:
        positions: (N, 3) current 3D positions in physical coordinates.
        velocities: (N, 3) current velocity vectors.

    Returns:
        (N, 3) predicted positions.
    """
    pos = np.asarray(positions, dtype=np.float32)
    vel = np.asarray(velocities, dtype=np.float32)
    return pos + vel


def update_velocity_ema(
    old_velocity: NDArray[np.float32], displacement: NDArray[np.float32], smoothing_factor: float
) -> NDArray[np.float32]:
    """
    Update velocity vector using exponential moving average (EMA).

    Args:
        old_velocity: (3,) prior estimated velocity vector.
        displacement: (3,) observed step displacement (new_pos - old_pos).
        smoothing_factor: Weight of the newly observed step in [0.0, 1.0].

    Returns:
        (3,) updated velocity vector.
    """
    old = np.asarray(old_velocity, dtype=np.float32)
    disp = np.asarray(displacement, dtype=np.float32)
    return np.astype((1.0 - smoothing_factor) * old + smoothing_factor * disp, np.float32)


def update_adaptive_sigma(
    residuals: NDArray[np.float32],
    current_sigma: NDArray[np.float32],
    momentum: float = 0.8,
) -> NDArray[np.float32]:
    """
    Update prediction uncertainty sigma per axis based on empirical residuals.

    Uses the Median Absolute Deviation (MAD) scaled by 1.4826 for robust Gaussian
    estimation, blended with previous sigma via momentum.

    Args:
        residuals: (M, 3) absolute prediction errors |cur_pos - pred_pos|.
        current_sigma: (3,) current uncertainty standard deviations per axis.
        momentum: Weight of existing sigma in EMA blend.

    Returns:
        (3,) updated uncertainty standard deviations.
    """
    if len(residuals) == 0:
        return current_sigma.copy()

    res = np.asarray(residuals, dtype=np.float32)
    median_residuals = np.median(res, axis=0)
    new_sigma = MAD_SCALE_FACTOR * median_residuals
    new_sigma = np.maximum(new_sigma, MIN_SIGMA_VALUE)

    curr = np.asarray(current_sigma, dtype=np.float32)
    return np.astype(momentum * curr + (1.0 - momentum) * new_sigma, np.float32)
