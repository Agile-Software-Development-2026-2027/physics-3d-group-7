"""
Unit tests for quantitative trajectory metrics calculation.

TODO: I want here too parametrized tests.
"""

import numpy as np
import pandas as pd
import pytest

from apkit4d.analysis.metrics import (
    STATS_COLUMNS,
    compute_track_statistics,
)


class TestComputeTrackStatistics:
    def test_empty_dataframe(self) -> None:
        """
        Verify empty DataFrame returns empty stats with correct schema."""
        empty_df = pd.DataFrame()
        stats = compute_track_statistics(empty_df)
        assert stats.empty
        assert list(stats.columns) == STATS_COLUMNS

    def test_missing_track_id_column(self) -> None:
        """
        Verify DataFrame without track ID column returns empty stats.
        """
        df = pd.DataFrame({"frame": [0, 1], "z_um": [0.0, 1.0], "y_um": [0.0, 0.0], "x_um": [0.0, 0.0]})
        stats = compute_track_statistics(df)
        assert stats.empty
        assert list(stats.columns) == STATS_COLUMNS

    def test_single_point_trajectory(self) -> None:
        """
        Verify metrics on a single-point trajectory (edge case).
        """
        df = pd.DataFrame(
            {
                "track_id": [0],
                "frame": [5],
                "z_um": [10.0],
                "y_um": [20.0],
                "x_um": [30.0],
                "reliability": [0.9],
                "margin_sigma": [5.0],
                "candidate_count": [1],
            }
        )
        stats = compute_track_statistics(df)
        assert len(stats) == 1
        row = stats.iloc[0]
        assert row["track_id"] == 0
        assert row["n_points"] == 1
        assert row["span_frames"] == 1
        assert row["n_gaps"] == 0
        assert row["path_length_um"] == 0.0
        assert row["net_displacement_um"] == 0.0
        assert np.isnan(row["duration_s"])
        assert np.isnan(row["median_step_um"])
        assert np.isnan(row["median_turn_deg"])
        assert np.isnan(row["frac_turn_gt_120"])
        assert row["mean_reliability"] == pytest.approx(0.9)
        assert row["min_reliability"] == pytest.approx(0.9)
        assert row["min_margin_sigma"] == pytest.approx(5.0)
        assert row["frac_uncertain_steps"] == pytest.approx(0.0)
        assert row["frac_contested_steps"] == pytest.approx(0.0)

    def test_straight_trajectory_with_timestamps_and_gaps(self) -> None:
        """
        Verify distance, speed, gap count, and duration on a known track.
        """
        # Track 0: moves 3 um along z per frame, has gap at frame 2
        # frames: 0, 1, 3, 4 (span 5, 1 gap)
        # step lengths: 3, 6, 3 -> sum = 12, median = 3
        # net displacement: 12 um
        # duration: 0.4 - 0.0 = 0.4 s
        df = pd.DataFrame(
            {
                "track_id": [0, 0, 0, 0],
                "frame": [0, 1, 3, 4],
                "z_um": [0.0, 3.0, 9.0, 12.0],
                "y_um": [0.0, 0.0, 0.0, 0.0],
                "x_um": [0.0, 0.0, 0.0, 0.0],
                "t_s": [0.0, 0.1, 0.3, 0.4],
                "reliability": [1.0, 0.8, 0.4, 0.9],
                "margin_sigma": [np.inf, 4.0, 2.0, np.inf],
                "candidate_count": [1, 2, 1, 1],
            }
        )

        stats = compute_track_statistics(df)
        assert len(stats) == 1
        row = stats.iloc[0]
        assert row["track_id"] == 0
        assert row["n_points"] == 4
        assert row["span_frames"] == 5
        assert row["n_gaps"] == 1
        assert row["path_length_um"] == pytest.approx(12.0)
        assert row["net_displacement_um"] == pytest.approx(12.0)
        assert row["duration_s"] == pytest.approx(0.4)
        assert row["median_step_um"] == pytest.approx(3.0)
        assert row["median_turn_deg"] == pytest.approx(0.0)
        assert row["frac_turn_gt_120"] == pytest.approx(0.0)

        # Reliability checks
        assert row["mean_reliability"] == pytest.approx(np.mean([1.0, 0.8, 0.4, 0.9]))
        assert row["min_reliability"] == pytest.approx(0.4)
        assert row["frac_uncertain_steps"] == pytest.approx(0.25)  # 1 out of 4 < 0.5
        assert row["min_margin_sigma"] == pytest.approx(2.0)
        assert row["frac_contested_steps"] == pytest.approx(0.25)  # 1 out of 4 > 1

    def test_sharp_turn_angle_calculation(self) -> None:
        """
        Verify turn angle calculation when particle performs a 180-degree reversal.
        """
        # Step 1: (0,0,0) -> (10,0,0) (direction +x)
        # Step 2: (10,0,0) -> (0,0,0)  (direction -x, 180 deg turn)
        df = pd.DataFrame(
            {
                "track_id": [0, 0, 0],
                "frame": [0, 1, 2],
                "z_um": [0.0, 0.0, 0.0],
                "y_um": [0.0, 0.0, 0.0],
                "x_um": [0.0, 10.0, 0.0],
            }
        )
        stats = compute_track_statistics(df)
        row = stats.iloc[0]
        assert row["median_turn_deg"] == pytest.approx(180.0)
        assert row["frac_turn_gt_120"] == pytest.approx(1.0)
        assert row["net_displacement_um"] == pytest.approx(0.0)
        assert row["path_length_um"] == pytest.approx(20.0)
