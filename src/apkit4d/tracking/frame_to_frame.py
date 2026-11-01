"""Frame-to-frame Linear Assignment Problem (LAP) particle tracking.

This module matches active trajectories to candidate detections in consecutive time frames
using minimum-cost bipartite matching, Monte Carlo prediction perturbation stability
scoring, and second-choice ambiguity margin estimation.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from apkit4d.core.models import TrackingConfig
from apkit4d.tracking.lap import LAPSolver, solve_sparse_lap
from apkit4d.tracking.motion import (
    predict_positions_ema,
    update_adaptive_sigma,
    update_velocity_ema,
)
from apkit4d.tracking.spatial import create_spatial_index

POSITION_COLUMNS = ["z_um", "y_um", "x_um"]


@dataclass(frozen=True)
class FrameLinkResult:
    """
    Output container for frame-to-frame matching results.
    """

    labels: NDArray[np.int32]
    reliability: NDArray[np.float32]
    margin_sigma: NDArray[np.float32]
    candidate_count: NDArray[np.int16]


def evaluate_mc_stability(
    predicted_positions: NDArray[np.float32],
    current_positions: NDArray[np.float32],
    candidate_rows: NDArray[np.int32],
    candidate_cols: NDArray[np.int32],
    matched_pairs: NDArray[np.int32],
    sigma: NDArray[np.float32],
    num_resamples: int,
    rng: np.random.Generator,
    lap_solver: LAPSolver = solve_sparse_lap,
) -> dict[tuple[int, int], float]:
    """
    Calculate connection stability via Monte Carlo perturbation of predictions.

    Args:
        predicted_positions: (A, 3) predicted positions of active tracks.
        current_positions: (B, 3) observed positions of current detections.
        candidate_rows: (E,) track indices for candidate edges.
        candidate_cols: (E,) detection indices for candidate edges.
        matched_pairs: (K, 2) accepted matches (track_idx, det_idx).
        sigma: (3,) prediction uncertainty standard deviation per coordinate (z, y, x).
        num_resamples: Number of Monte Carlo iterations (e.g. 20).
        rng: NumPy random generator.
        lap_solver: LAP solver function.

    Returns:
        Mapping of (track_idx, det_idx) to fraction of resamples where the match held.

    RefactorNote:
        Equivalent of lines 179-191 in legacy `link_frame_to_frame`.
    """
    if num_resamples <= 0 or len(matched_pairs) == 0:
        return {}

    pair_counts: dict[tuple[int, int], int] = {(int(a), int(b)): 0 for a, b in matched_pairs}
    num_active = len(predicted_positions)
    num_current = len(current_positions)

    for _ in range(num_resamples):
        # Perturb the prediction, not the detection: that is where uncertainty lies
        noise = rng.normal(0.0, sigma, size=predicted_positions.shape).astype(np.float32)
        perturbed_pred = predicted_positions + noise
        pert_costs = np.sum(
            (perturbed_pred[candidate_rows] - current_positions[candidate_cols]) ** 2,
            axis=1,
        )
        resampled_matches = lap_solver(candidate_rows, candidate_cols, pert_costs, num_active, num_current)
        for r_a, r_b in resampled_matches:
            pair_key = (int(r_a), int(r_b))
            if pair_key in pair_counts:
                pair_counts[pair_key] += 1

    return {k: v / num_resamples for k, v in pair_counts.items()}


def compute_assignment_margins(
    predicted_positions: NDArray[np.float32],
    current_positions: NDArray[np.float32],
    candidate_rows: NDArray[np.int32],
    candidate_cols: NDArray[np.int32],
    matched_pairs: NDArray[np.int32],
    sigma: NDArray[np.float32],
) -> tuple[dict[tuple[int, int], float], dict[int, int]]:
    """
    Compute ambiguity margins and candidate counts for accepted matches.

    The margin is the distance to the closest alternative candidate minus the distance
    to the chosen candidate, normalized by the effective sigma.

    Args:
        predicted_positions: (A, 3) predicted positions.
        current_positions: (B, 3) observed positions.
        candidate_rows: (E,) candidate edge source indices.
        candidate_cols: (E,) candidate edge target indices.
        matched_pairs: (K, 2) chosen matches.
        sigma: (3,) coordinate uncertainties.

    Returns:
        Tuple of (margin_dict, candidate_counts_per_track).

    RefactorNote:
        Equivalent of the margin and alternative candidate calculation block
        (lines 192-215) in legacy `link_frame_to_frame`.
    """
    if len(matched_pairs) == 0:
        return {}, {}

    # Margin: distance of the best ALTERNATIVE minus the chosen one, in units of
    # σ(sigma) of the prediction. Needed because the Monte Carlo score saturates
    # when alternatives are distant: there it only reports "no ambiguity",
    # while the margin continues to distinguish a comfortable case from a borderline
    # one. Both sides are checked: other detections for that track, and other
    # tracks that claim that detection.
    sigma_eff = float(np.sqrt(np.mean(sigma**2)))
    edge_distances = np.sqrt(
        np.sum(
            (predicted_positions[candidate_rows] - current_positions[candidate_cols]) ** 2,
            axis=1,
        )
    )

    chosen_set = {(int(a), int(b)) for a, b in matched_pairs}
    best_alt_for_track: dict[int, float] = {}
    best_alt_for_det: dict[int, float] = {}

    for idx, (ia, ib) in enumerate(zip(candidate_rows, candidate_cols, strict=True)):
        key = (int(ia), int(ib))
        if key in chosen_set:
            continue
        dist = float(edge_distances[idx])
        best_alt_for_track[int(ia)] = min(best_alt_for_track.get(int(ia), np.inf), dist)
        best_alt_for_det[int(ib)] = min(best_alt_for_det.get(int(ib), np.inf), dist)

    chosen_distances = {
        (int(a), int(b)): float(np.linalg.norm(predicted_positions[a] - current_positions[b]))
        for a, b in matched_pairs
    }

    margins: dict[tuple[int, int], float] = {}
    candidate_counts: dict[int, int] = {}

    for a, b in matched_pairs:
        ia, ib = int(a), int(b)
        alt = min(best_alt_for_track.get(ia, np.inf), best_alt_for_det.get(ib, np.inf))
        chosen_dist = chosen_distances[(ia, ib)]
        margins[(ia, ib)] = (alt - chosen_dist) / sigma_eff if np.isfinite(alt) else np.inf
        candidate_counts[ia] = int(np.sum(candidate_rows == ia))

    return margins, candidate_counts


def link_consecutive_frames(
    detections: pd.DataFrame,
    config: TrackingConfig,
    seed: int = 0,
    lap_solver: LAPSolver = solve_sparse_lap,
) -> FrameLinkResult:
    """
    Perform frame-to-frame trajectory linking detections with Monte Carlo stability scoring.

    Connection reliability is computed as in u-track3D (Cell Rep Methods 2023): the PREDICTED
    position of each track is resampled N times and the assignment rerun; the score is the
    fraction of resamples that keep the same connection. A score of 1 means no ambiguity,
    a score of 0 means the outcome hinges entirely on the prediction.

    The resampling spread is not set a priori: it is estimated per axis from the actual
    residuals (observed minus predicted position) of accepted matches in previously processed
    frames. That is the point, the score does not assume the motion model is correct for this
    sample. If it is not, residuals and perturbations grow larger and scores drop accordingly:
    the method reports on its own that predictions are unreliable for these data.

    Args:
        detections: Standardized detections table sorted by frame.
        config: Tracking configuration parameters.
        seed: Random seed for Monte Carlo perturbations.
        lap_solver: Bipartite matching solver.

    Returns:
        FrameLinkResult containing assigned segment labels, reliability, margin, and candidate counts.

    RefactorNote:
        Equivalent of `link_frame_to_frame` from legacy `link.py` (lines 130-248).
    """
    det = detections.reset_index(drop=True)
    num_detections = len(det)
    labels = np.full(num_detections, -1, dtype=np.int32)
    reliability = np.full(num_detections, np.nan, dtype=np.float32)
    # How much further away the second choice was, in units of σ(sigma)
    margin_sigma = np.full(num_detections, np.nan, dtype=np.float32)
    candidate_count = np.zeros(num_detections, dtype=np.int16)

    if num_detections == 0:
        return FrameLinkResult(labels, reliability, margin_sigma, candidate_count)

    frame_arr = det["frame"].to_numpy(dtype=np.int64)
    frames, split_points = np.unique(frame_arr, return_index=True)

    all_indices = np.arange(num_detections, dtype=np.int64)
    grouped = np.split(all_indices, split_points[1:])

    frame_indices: dict[int, NDArray[np.int64]] = dict(zip((int(x) for x in frames), grouped, strict=True))

    coords = det[POSITION_COLUMNS].to_numpy(dtype=np.float32)
    rng = np.random.default_rng(seed)

    active_labels: list[int] = []
    active_positions: list[NDArray[np.float32]] = []
    active_velocities: list[NDArray[np.float32]] = []
    num_tracks = 0
    gate_squared = config.max_dist_um**2

    # Initial dispersion: one third of the search radius, later replaced by data
    sigma = np.full(3, config.max_dist_um / 3.0, dtype=np.float32)

    for f in frames:
        current_idx = frame_indices[int(f)]
        current_coords = coords[current_idx]
        matched_pairs = np.empty((0, 2), dtype=np.int32)

        if active_labels:
            pred_positions = predict_positions_ema(
                positions=np.array(active_positions, dtype=np.float32),
                velocities=np.array(active_velocities, dtype=np.float32),
            )
            spatial_index = create_spatial_index(current_coords)
            candidates: list[list[int]] = spatial_index.query_radius(pred_positions, config.max_dist_um)

            row_list: list[int] = []
            col_list: list[int] = []
            for track_idx, match_cand in enumerate(candidates):
                for det_idx in match_cand:
                    row_list.append(track_idx)
                    col_list.append(det_idx)

            if row_list:
                cand_rows = np.array(row_list, dtype=np.int32)
                cand_cols = np.array(col_list, dtype=np.int32)
                costs = np.sum((pred_positions[cand_rows] - current_coords[cand_cols]) ** 2, axis=1)
                valid_mask = costs <= gate_squared
                cand_rows = cand_rows[valid_mask]
                cand_cols = cand_cols[valid_mask]
                costs = costs[valid_mask]

                matched_pairs = lap_solver(
                    cand_rows, cand_cols, costs, len(active_labels), len(current_coords)
                )

                if config.mc_resamples > 0 and len(matched_pairs) > 0:
                    stabilities = evaluate_mc_stability(
                        pred_positions,
                        current_coords,
                        cand_rows,
                        cand_cols,
                        matched_pairs,
                        sigma,
                        config.mc_resamples,
                        rng,
                        lap_solver,
                    )
                    for a, b in matched_pairs:
                        reliability[current_idx[b]] = stabilities.get((int(a), int(b)), 0.0)

                if len(matched_pairs) > 0:
                    margins, cand_counts = compute_assignment_margins(
                        pred_positions,
                        current_coords,
                        cand_rows,
                        cand_cols,
                        matched_pairs,
                        sigma,
                    )
                    for a, b in matched_pairs:
                        ia, ib = int(a), int(b)
                        margin_sigma[current_idx[ib]] = margins.get((ia, ib), np.nan)
                        candidate_count[current_idx[ib]] = cand_counts.get(ia, 0)

                    # Residuals: how much the prediction actually deviated on this frame
                    residuals = np.abs(
                        current_coords[matched_pairs[:, 1]] - pred_positions[matched_pairs[:, 0]]
                    )
                    sigma = update_adaptive_sigma(residuals, sigma)

        # Track lists are rebuilt from scratch each frame: only tracks with a detection
        # in THIS frame remain active (either continued or newly initiated). Tracks left
        # without a match close here; gap closing handles reconnecting any missing detections.
        next_labels: list[int] = []
        next_positions: list[NDArray[np.float32]] = []
        next_velocities: list[NDArray[np.float32]] = []
        matched_detections = set(matched_pairs[:, 1].tolist()) if len(matched_pairs) else set()

        for a, b in matched_pairs:
            ia, ib = int(a), int(b)
            new_pos = current_coords[ib]
            displacement = new_pos - active_positions[ia]
            updated_vel = update_velocity_ema(active_velocities[ia], displacement, config.velocity_smoothing)

            next_labels.append(active_labels[ia])
            next_positions.append(new_pos)
            next_velocities.append(updated_vel)
            labels[current_idx[ib]] = active_labels[ia]

        for det_pos_idx in range(len(current_coords)):
            if det_pos_idx in matched_detections:
                continue
            labels[current_idx[det_pos_idx]] = num_tracks
            next_labels.append(num_tracks)
            next_positions.append(current_coords[det_pos_idx])
            next_velocities.append(np.zeros(3, dtype=np.float32))
            num_tracks += 1

        active_labels = next_labels
        active_positions = next_positions
        active_velocities = next_velocities

    return FrameLinkResult(
        labels=labels,
        reliability=reliability,
        margin_sigma=margin_sigma,
        candidate_count=candidate_count,
    )


"""
TODO: frame indices this way are inefficient

We should Migarte:
    frame_arr = det["frame"].to_numpy(dtype=np.int64)
    frames, split_points = np.unique(frame_arr, return_index=True)

    all_indices = np.arange(num_detections, dtype=np.int64)
    grouped = np.split(all_indices, split_points[1:])

    frame_indices: dict[int, NDArray[np.int64]] = dict(zip((int(x) for x in frames), grouped, strict=True))
To something like this:
frame_arr = det["frame"].to_numpy(dtype=np.int64)
    frames = np.unique(frame_arr)

    split_idx = np.searchsorted(frame_arr, frames)
    ends = np.append(split_idx[1:], len(det))
this woudl also require updating the for
    for f, start, end in zip(frames, split_idx, ends):
        cur = coords[start:end]
        ...
        for a, b in matched_pairs:
            labels[start + b] = active_labels[a]
            
I did not doo this because I'm not competent enough to be sure
Ill ask Giusy to chekc if I'm missing something
"""
