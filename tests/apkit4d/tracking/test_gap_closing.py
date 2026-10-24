"""
Unit tests for trajectory gap closing and DisjointSetUnion data structure.

RefactorNote:

"""

import numpy as np
import pandas as pd

from apkit4d.core.models import TrackingConfig
from apkit4d.tracking.gap_closing import DisjointSetUnion, close_trajectory_gaps


class TestCloseTrajectoryGaps:
    def test_close_trajectory_gaps_disabled(self) -> None:
        """
        Verify that max_gap=0 returns unchanged labels.
        """
        cfg = TrackingConfig(max_gap=0)
        df = pd.DataFrame(
            {
                "frame": [0, 1, 3, 4],
                "z_um": [0.0, 1.0, 3.0, 4.0],
                "y_um": [0.0, 0.0, 0.0, 0.0],
                "x_um": [0.0, 0.0, 0.0, 0.0],
            }
        )
        labels = np.array([0, 0, 1, 1], dtype=np.int32)
        res = close_trajectory_gaps(df, labels, cfg)
        np.testing.assert_array_equal(res, labels)

    def test_close_trajectory_gaps_bridges_missing_frame(self) -> None:
        """
        Verify bridging a single missing frame (frame 2 missing between 1 and 3).
        """
        cfg = TrackingConfig(max_gap=2, gap_dist_um=25.0)
        df = pd.DataFrame(
            {
                "frame": [0, 1, 3, 4],
                "z_um": [10.0, 11.0, 13.0, 14.0],
                "y_um": [0.0, 0.0, 0.0, 0.0],
                "x_um": [0.0, 0.0, 0.0, 0.0],
            }
        )
        labels = np.array([0, 0, 1, 1], dtype=np.int32)
        res = close_trajectory_gaps(df, labels, cfg)

        assert res[0] == res[2]
        assert len(np.unique(res)) == 1

    def test_close_trajectory_gaps_empty_df(self) -> None:
        """
        Verify gap closing handles empty DataFrames.
        """
        cfg = TrackingConfig()
        df = pd.DataFrame(columns=["frame", "z_um", "y_um", "x_um"])
        labels = np.empty(0, dtype=np.int32)
        res = close_trajectory_gaps(df, labels, cfg)
        assert len(res) == 0


class TestDisjointSetUnion:
    """
    Unit tests for the DisjointSetUnion class.
    """

    def test_dsu_basic_operations(self) -> None:
        """
        Verify initialization, find, and union.
        """
        dsu: DisjointSetUnion[int] = DisjointSetUnion([1, 2, 3, 4, 5])
        assert dsu.find(1) == 1
        assert dsu.find(2) == 2

        dsu.union(1, 2)
        assert dsu.find(1) == dsu.find(2)

        dsu.union(2, 3)
        assert dsu.find(3) == dsu.find(1)
        assert dsu.find(4) == 4

    def test_dsu_dynamic_addition(self) -> None:
        """
        Verify adding elements on the fly and finding unadded elements.
        """
        dsu: DisjointSetUnion[str] = DisjointSetUnion()
        # Find on unadded element should automatically add and return it
        assert dsu.find("gamma") == "gamma"

        dsu.add("alpha")
        dsu.add("beta")
        assert dsu.find("alpha") == "alpha"

        dsu.union("alpha", "beta")
        assert dsu.find("beta") == dsu.find("alpha")
