"""
Unit tests for sparse LAP bipartite assignment solver.

Note:
    I migth moce this inside a `lap` folder if the LAP solver grows into multiple files.
"""

import numpy as np

from apkit4d.tracking.lap import solve_sparse_lap


class TestSolveSparseLAP:
    def test_solve_sparse_lap_empty(self) -> None:
        """
        Verify solver with zero candidate edges.
        """
        rows = np.empty(0, dtype=np.int32)
        cols = np.empty(0, dtype=np.int32)
        costs = np.empty(0, dtype=np.float32)

        res = solve_sparse_lap(rows, cols, costs, n_a=5, n_b=5)
        assert res.shape == (0, 2)

    def test_solve_sparse_lap_trivial_single_edge(self) -> None:
        """
        Verify solver works on trivial 1-to-1 components.

        We only have 0 -> 0 and 1 -> 1 edges, so the solver should return both pairs.
        """
        rows = np.array([0, 1], dtype=np.int32)
        cols = np.array([0, 1], dtype=np.int32)
        costs = np.array([2.5, 3.0], dtype=np.float32)

        res = solve_sparse_lap(rows, cols, costs, n_a=2, n_b=2)
        assert res.shape == (2, 2)
        pairs = {tuple(p) for p in res.tolist()}
        assert pairs == {(0, 0), (1, 1)}

    def test_solve_sparse_lap_ambiguous_competition(self) -> None:
        """
        Verify solver when two tracks compete for the same detection.

        Track 0 and Track 1 both compete for detection 0 and detection 1
        Costs:
          0 -> 0: cost 1.0, 0 -> 1: cost 5.0
          1 -> 0: cost 2.0, 1 -> 1: cost 2.5
        Optimal matching:
          0 -> 0 (cost 1.0) + 1 -> 1 (cost 2.5) = total 3.5
        Non-optimal:
          0 -> 1 (5.0) + 1 -> 0 (2.0) = total 7.0
        """
        rows = np.array([0, 0, 1, 1], dtype=np.int32)
        cols = np.array([0, 1, 0, 1], dtype=np.int32)
        costs = np.array([1.0, 5.0, 2.0, 2.5], dtype=np.float32)

        res = solve_sparse_lap(rows, cols, costs, n_a=2, n_b=2)
        pairs = {tuple(p) for p in res.tolist()}
        assert pairs == {(0, 0), (1, 1)}

    def test_solve_sparse_lap_unmatched_due_to_cost(self) -> None:
        """
        Verify that edges above UNMATCHED_COST are not assigned.

        In single edge component, it directly pairs since len(unique_rows)==1 and len(unique_cols)==1,
        but in a component with multiple identical choices we have ambiguity.
        Basically we have a single detect to match to 2 detects that have teh same cost.
        Since no one is better than the otehr we'0re not able to match any.
        """
        rows = np.array([0, 0], dtype=np.int32)
        cols = np.array([0, 1], dtype=np.int32)
        costs = np.array([1e15, 1e15], dtype=np.float32)

        res = solve_sparse_lap(rows, cols, costs, n_a=1, n_b=2)
        assert len(res) == 0
