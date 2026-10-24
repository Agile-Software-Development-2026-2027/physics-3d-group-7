"""Unit tests for biophysical motility analysis and direction autocorrelation."""

import numpy as np
import pandas as pd

from apkit4d.analysis.motility import compute_direction_acf


class TestComputeDirectionACF:
    def test_empty_dataframe(self) -> None:
        """Verify empty tracks DataFrame returns empty arrays."""
        empty_df = pd.DataFrame()
        lags, acf = compute_direction_acf(empty_df)
        assert len(lags) == 0
        assert len(acf) == 0

    def test_invalid_max_lag(self) -> None:
        """Verify max_lag < 1 returns empty arrays."""
        df = pd.DataFrame({"track_id": [0], "frame": [0], "z_um": [0.0], "y_um": [0.0], "x_um": [0.0]})
        lags, acf = compute_direction_acf(df, max_lag=0)
        assert len(lags) == 0
        assert len(acf) == 0

    def test_tracks_below_min_points_ignored(self) -> None:
        """Verify trajectories with fewer detections than min_points are ignored."""
        # 10 points < default min_points 20
        rows = []
        for f in range(10):
            rows.append({"track_id": 0, "frame": f, "z_um": float(f), "y_um": 0.0, "x_um": 0.0})
        df = pd.DataFrame(rows)

        lags, acf = compute_direction_acf(df, max_lag=5, min_points=20)
        assert len(lags) == 0
        assert len(acf) == 0

    def test_straight_line_swimmer_acf_equals_one(self) -> None:
        """Verify that a straight trajectory yields an autocorrelation of exactly 1.0."""
        # 25 points moving in a constant direction
        rows = []
        for f in range(25):
            rows.append(
                {
                    "track_id": 0,
                    "frame": f,
                    "z_um": float(f) * 2.0,
                    "y_um": float(f) * 1.5,
                    "x_um": float(f) * -0.5,
                }
            )
        df = pd.DataFrame(rows)

        lags, acf = compute_direction_acf(df, max_lag=5, min_points=20)
        assert len(lags) == 5
        np.testing.assert_array_equal(lags, np.arange(1, 6))
        np.testing.assert_allclose(acf, np.ones(5), rtol=1e-6)

    def test_multiple_tracks_combination(self) -> None:
        """Verify pooling across multiple tracks."""
        rows = []
        # Track 0: straight along +z (25 points)
        for f in range(25):
            rows.append({"track_id": 0, "frame": f, "z_um": float(f), "y_um": 0.0, "x_um": 0.0})
        # Track 1: straight along +y (25 points)
        for f in range(25):
            rows.append({"track_id": 1, "frame": f, "z_um": 0.0, "y_um": float(f), "x_um": 0.0})
        # Track 2: short track (5 points, should be skipped)
        for f in range(5):
            rows.append({"track_id": 2, "frame": f, "z_um": 100.0, "y_um": 100.0, "x_um": 100.0})

        df = pd.DataFrame(rows)
        lags, acf = compute_direction_acf(df, max_lag=3, min_points=20)
        assert len(lags) == 3
        np.testing.assert_allclose(acf, [1.0, 1.0, 1.0], rtol=1e-6)
