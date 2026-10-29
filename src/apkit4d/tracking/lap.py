"""
Linear Assignment Problem (LAP) solvers for bipartite tracking graphs.

This module decomposes large bipartite candidate matchings into connected components
using sparse graph traversal. Trivial 1-to-1 components are solved immediately, while
ambiguous components are solved via linear sum assignment. This decomposition keeps
optimization time minimal even for thousands of particles.
This is basically used to `optimize` other parts of teh code while running on the CPU.
This may not find an use when/if we move the processing on GPU.
This mopdule is part of the LAP solver that follows this concept:
    If you have N workers and N jobs, and every worker has a specific cost to do each task,
    or different tak takes different times, how do you assign jobs to each workers
    so that the total cost is as low as possible?
While this is not truly our use case this gives the idea of what problem this tries to achive.
"""

from typing import Protocol

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import linear_sum_assignment
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

UNMATCHED_COST: float = 1e12  # Alias of legacy BIG


class LAPSolver(Protocol):
    """
    Protocol for bipartite matching optimization solvers.

    RefactorNote:
        What is this garbage, this is a "gracious"way to make an "interface" in python
        This atrocity is needed because we're developing in a language that was created only for scripting
        and became too much...
        Are we planning on actually using what the interface offer in the cose? absolutely not
        Is this going to make coding easier? only if teh code grew a lot, so no
        Am I still doing this? yes, also because this is ONLY for type checker happyness
    """

    def __call__(
        self,
        rows: NDArray[np.int32],
        cols: NDArray[np.int32],
        costs: NDArray[np.float32],
        n_a: int,
        n_b: int,
    ) -> NDArray[np.int32]:
        """Solve minimum-cost bipartite assignment on candidate edges.

        Args:
            rows: (E,) integer array of source candidate indices in [0, n_a - 1].
            cols: (E,) integer array of target candidate indices in [0, n_b - 1].
            costs: (E,) float array of edge weights (e.g. squared Euclidean distances).
            n_a: Number of source entities (e.g. active tracks).
            n_b: Number of target entities (e.g. current frame detections).

        Returns:
            (K, 2) array of matched (row_idx, col_idx) pairs.
        """
        ...


def solve_sparse_lap(
    rows: NDArray[np.int32],
    cols: NDArray[np.int32],
    costs: NDArray[np.float32],
    n_a: int,
    n_b: int,
) -> NDArray[np.int32]:
    """Solve minimum-cost bipartite assignment by decomposing into connected components.

    Args:
        rows: Source node indices of candidate edges.
        cols: Target node indices of candidate edges.
        costs: Weights of candidate edges.
        n_a: Total count of source nodes.
        n_b: Total count of target nodes.

    Returns:
        (K, 2) array of optimal matched pairs [source_index, target_index].

    RefactorNote:
        Whilst this function seems quite a bit different if you analize it closely you will notice
        it is basically the same as the legacy `solve_lap` but with clearer variables names, comments
        and expandedn assignments to makke it easier to read and understand.
        In particular single letter variables were removed as much as I tougth it was needed (all of them)
        Yeah `idx` instead of `i` is redundant but I could not have said `all of them` in that case.
    """
    if len(rows) == 0:
        return np.empty((0, 2), dtype=np.int32)

    rows_arr = np.asarray(rows, dtype=np.int32)
    cols_arr = np.asarray(cols, dtype=np.int32)
    costs_arr = np.asarray(costs, dtype=np.float32)

    total_nodes = n_a + n_b
    adj = coo_matrix(
        (np.ones(len(rows_arr), dtype=np.float32), (rows_arr, cols_arr + n_a)),
        shape=(total_nodes, total_nodes),
    )
    _, labels = connected_components(adj + adj.T, directed=False)

    component_of_edge = labels[rows_arr]
    order = np.argsort(component_of_edge, kind="stable")
    rows_sorted = rows_arr[order]
    cols_sorted = cols_arr[order]
    costs_sorted = costs_arr[order]
    comp_sorted = component_of_edge[order]

    # Note: unique_comps were not use in the old code too
    #       I left them there because I do no know what to do wioth them
    unique_comps, starts = np.unique(comp_sorted, return_index=True)
    matched_pairs: list[tuple[int, int]] = []

    for idx, start_pos in enumerate(starts):
        end_pos = starts[idx + 1] if idx + 1 < len(starts) else len(rows_sorted)
        r_comp = rows_sorted[start_pos:end_pos]
        c_comp = cols_sorted[start_pos:end_pos]
        w_comp = costs_sorted[start_pos:end_pos]

        unique_rows, inv_rows = np.unique(r_comp, return_inverse=True)
        unique_cols, inv_cols = np.unique(c_comp, return_inverse=True)

        # Trivial case: single source, single target (no ambiguity)
        if len(unique_rows) == 1 and len(unique_cols) == 1:
            matched_pairs.append((int(unique_rows[0]), int(unique_cols[0])))
            continue

        cost_matrix = np.full((len(unique_rows), len(unique_cols)), UNMATCHED_COST, dtype=np.float64)
        cost_matrix[inv_rows, inv_cols] = w_comp

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        for r_i, c_i in zip(row_ind, col_ind, strict=True):
            if cost_matrix[r_i, c_i] < UNMATCHED_COST:
                matched_pairs.append((int(unique_rows[r_i]), int(unique_cols[c_i])))

    if not matched_pairs:
        return np.empty((0, 2), dtype=np.int32)

    return np.array(matched_pairs, dtype=np.int32)
