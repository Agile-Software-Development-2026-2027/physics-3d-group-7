"""
Unit tests for motion modeling and kinematics.

RefactorNote:
    I did not know before this that numpy could have been used for testing
    with assert integrated in the library itself... noice.
"""

import numpy as np
import pytest

from apkit4d.tracking.motion import (
    compute_search_gate,
    predict_positions_ema,
    update_adaptive_sigma,
    update_velocity_ema,
)


def test_compute_search_gate() -> None:
    """
    Verify search gate calculation from frame time delta.
    """
    assert compute_search_gate(0.1, 250.0) == 25.0
    assert compute_search_gate(0.05, 200.0) == 10.0

    with pytest.raises(ValueError):
        compute_search_gate(0.0)

    with pytest.raises(ValueError):
        compute_search_gate(0.1, -10.0)


def test_predict_positions_ema() -> None:
    """
    Verify EMA position prediction.
    """
    pos = np.array([[10.0, 20.0, 30.0], [5.0, 5.0, 5.0]], dtype=np.float32)
    vel = np.array([[1.0, -2.0, 3.0], [0.0, 1.0, 2.0]], dtype=np.float32)

    pred = predict_positions_ema(pos, vel)
    expected = np.array([[11.0, 18.0, 33.0], [5.0, 6.0, 7.0]], dtype=np.float32)
    np.testing.assert_allclose(pred, expected)


def test_update_velocity_ema() -> None:
    """
    Verify EMA velocity vector updating.
    """
    old_vel = np.array([10.0, 0.0, 0.0], dtype=np.float32)
    disp = np.array([20.0, 10.0, 0.0], dtype=np.float32)

    updated = update_velocity_ema(old_vel, disp, smoothing_factor=0.5)
    expected = np.array([15.0, 5.0, 0.0], dtype=np.float32)
    np.testing.assert_allclose(updated, expected)


def test_update_adaptive_sigma() -> None:
    """
    Verify adaptive uncertainty update.
    """
    residuals = np.array(
        [
            [1.0, 2.0, 0.5],
            [1.2, 1.8, 0.4],
            [0.8, 2.2, 0.6],
        ],
        dtype=np.float32,
    )
    current_sigma = np.array([2.0, 2.0, 2.0], dtype=np.float32)

    updated = update_adaptive_sigma(residuals, current_sigma, momentum=0.8)
    assert len(updated) == 3
    assert np.all(updated > 0)

    empty_residuals = np.empty((0, 3), dtype=np.float32)
    unchanged = update_adaptive_sigma(empty_residuals, current_sigma)
    np.testing.assert_allclose(unchanged, current_sigma)
