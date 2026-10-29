"""
Multi-frame gap closing and trajectory segment stitching.

This module bridges temporary missing detections by extrapolating trajectory endpoints
using estimated tail velocities, finding compatible segment start points across gaps
up to max_gap frames, solving a global LAP assignment, and merging chains via a
Disjoint-Set Union (DSU) data structure.

RefactorNote:
    It is not that hard to make but of course everything needs to be in numpy so a bit harder
    than normal python... I split it with comments but if it is hard to understand ask GOD
    because a week after I wrote this code he will be the only one who knows anything about it.
"""

from collections.abc import Hashable

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from apkit4d.core.models import TrackingConfig
from apkit4d.tracking.lap import LAPSolver, solve_sparse_lap
from apkit4d.tracking.spatial import create_spatial_index

POSITION_COLUMNS = ["z_um", "y_um", "x_um"]


class DisjointSetUnion[T: Hashable]:
    """
    Disjoint-Set Union (DSU / Union-Find) with path compression and rank optimization.
    """

    def __init__(self, elements: set[T] | list[T] | None = None) -> None:
        """
        Initialize the DSU structure.
        """
        self._parent: dict[T, T] = {}
        self._rank: dict[T, int] = {}
        if elements is not None:
            for elem in elements:
                self.add(elem)

    def add(self, x: T) -> None:
        """
        Add an element if not already present.
        """
        if x not in self._parent:
            self._parent[x] = x
            self._rank[x] = 0

    def find(self, x: T) -> T:
        """
        Find the root representative of the set containing x with path compression.
        """
        if x not in self._parent:
            self.add(x)
            return x

        root = x
        while self._parent[root] != root:
            root = self._parent[root]

        curr = x
        while curr != root:
            nxt = self._parent[curr]
            self._parent[curr] = root
            curr = nxt

        return root

    def union(self, root_a: T, root_b: T) -> T:
        """
        Merge the set of root_b into root_a.

        To strictly preserve trajectory directionality (earlier segment is parent of later segment),
        root_b becomes a child of root_a.

        Args:
            root_a: Leader representative of first component.
            root_b: Leader representative of second component.

        Returns:
            The resulting set representative.
        """
        rep_a = self.find(root_a)
        rep_b = self.find(root_b)
        if rep_a != rep_b:
            self._parent[rep_b] = rep_a
        return rep_a


def close_trajectory_gaps(
    detections: pd.DataFrame,
    segment_labels: NDArray[np.int32],
    config: TrackingConfig,
    lap_solver: LAPSolver = solve_sparse_lap,
) -> NDArray[np.int32]:
    """
    Stitch broken trajectory segments across missing detection frames.

    Args:
        detections: DataFrame containing at least ['frame', 'z_um', 'y_um', 'x_um'].
        segment_labels: (N,) array of segment labels from frame-to-frame linking.
        config: Tracking parameters including max_gap and gap_dist_um.
        lap_solver: Bipartite matching optimization solver.

    Returns:
        (N,) updated array of consolidated trajectory labels.

    RefactorNote:
        I'm happy, the time I wasted on the Interfaces was used here too
    """
    if config.max_gap < 1 or len(detections) == 0:
        return np.asarray(segment_labels, dtype=np.int32)

    df = detections.assign(_segment_id=segment_labels)
    grouped = df.groupby("_segment_id")

    first_points = grouped.first()
    last_points = grouped.last()
    unique_labels = last_points.index.to_numpy()
    segment_lengths = grouped.size().to_numpy()

    end_positions = last_points[POSITION_COLUMNS].to_numpy(dtype=np.float32)
    end_frames = last_points["frame"].to_numpy(dtype=np.int32)
    start_positions = first_points[POSITION_COLUMNS].to_numpy(dtype=np.float32)
    start_frames = first_points["frame"].to_numpy(dtype=np.int32)

    # Estimate tail velocity from the last up to 3 points in each segment
    tail_grouped = df.groupby("_segment_id").tail(3).groupby("_segment_id")
    pos_tail_last = tail_grouped[POSITION_COLUMNS].last().to_numpy(dtype=np.float32)
    pos_tail_first = tail_grouped[POSITION_COLUMNS].first().to_numpy(dtype=np.float32)
    frame_tail_last = tail_grouped["frame"].last().to_numpy(dtype=np.float32)
    frame_tail_first = tail_grouped["frame"].first().to_numpy(dtype=np.float32)

    delta_pos = pos_tail_last - pos_tail_first
    delta_frame = np.maximum(1.0, frame_tail_last - frame_tail_first)
    tail_velocity = delta_pos / delta_frame[:, None]

    # For single-point segments, velocity is unknown (set to 0)
    tail_velocity = np.where((segment_lengths >= 2)[:, None], tail_velocity, 0.0)

    rows: list[int] = []
    cols: list[int] = []
    costs: list[float] = []

    start_index = create_spatial_index(start_positions)
    num_segments = len(unique_labels)

    # Search across gaps: gap=1 corresponds to consecutive frames, up to max_gap + 1
    for gap in range(1, config.max_gap + 2):
        predicted_pos = end_positions + tail_velocity * gap
        search_radius = float(config.gap_dist_um * gap)
        candidate_lists = start_index.query_radius(predicted_pos, search_radius)

        for end_idx, start_candidates in enumerate(candidate_lists):
            for start_idx in start_candidates:
                if start_frames[start_idx] - end_frames[end_idx] != gap:
                    continue
                displacement = predicted_pos[end_idx] - start_positions[start_idx]
                cost = float(np.sum(displacement**2))
                rows.append(end_idx)
                cols.append(start_idx)
                costs.append(cost)

    if not rows:
        return np.asarray(segment_labels, dtype=np.int32)

    matched_pairs = lap_solver(
        np.array(rows, dtype=np.int32),
        np.array(cols, dtype=np.int32),
        np.array(costs, dtype=np.float32),
        num_segments,
        num_segments,
    )

    dsu: DisjointSetUnion[int] = DisjointSetUnion([int(lab) for lab in unique_labels])
    for end_idx, start_idx in matched_pairs:
        dsu.union(int(unique_labels[end_idx]), int(unique_labels[start_idx]))

    consolidated_labels = np.array([dsu.find(int(lab)) for lab in segment_labels], dtype=np.int32)
    return consolidated_labels
