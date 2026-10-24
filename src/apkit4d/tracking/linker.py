"""Master ParticleLinker engine coordinating multi-frame trajectory tracking.

This module provides the main entry point for tracking detected particles across time.
It coordinates frame-to-frame LAP matching, gap closing, track length filtering,
and canonical track ID ordering.

RefactorNote:
    It may be becausedifferences startes to stack but this was a tad harder than the others IDK.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from apkit4d.core.models import TrackingConfig
from apkit4d.tracking.frame_to_frame import link_consecutive_frames
from apkit4d.tracking.gap_closing import close_trajectory_gaps
from apkit4d.tracking.lap import LAPSolver, solve_sparse_lap

REQUIRED_COLUMNS: list[str] = ["frame", "z_um", "y_um", "x_um"]


@dataclass(frozen=True)
class TrackingResult:
    """
    Result returned by `ParticleLinker.link()`, check the `ParticleLinker` class for more details.
    """

    tracks: pd.DataFrame
    metadata: dict[str, Any]


class ParticleLinker:
    """
    Coordinator for particle tracking and trajectory linking.
    """

    def __init__(
        self,
        config: TrackingConfig | None = None,
        lap_solver: LAPSolver = solve_sparse_lap,
    ) -> None:
        """
        Initialize the linker with configuration and LAP solver.

        Args:
            config: Tracking configuration parameters. If None, default config is used.
            lap_solver: Bipartite matching solver callable.
        """
        self.config = config or TrackingConfig()
        self.lap_solver = lap_solver

    def link(self, detections: pd.DataFrame, seed: int = 0) -> TrackingResult:
        """
        Link particle detections across frames into continuous trajectories.

        Args:
            detections: Input DataFrame with at least ['frame', 'z_um', 'y_um', 'x_um'].
            seed: Random seed for Monte Carlo stability perturbations.

        Returns:
            TrackingResult with tracked DataFrame and summary metadata.

        RefactorNore:
            Technically we could have added a dataClass for the metadata instead of using a dict, but we're in
            python and python is garbage for stuff like this, so since I hate using decorators for data
            classes I will use as less as possible.
        """
        if detections.empty:
            empty_tracks = pd.DataFrame(
                columns=list(detections.columns)
                + ["track_id", "reliability", "margin_sigma", "candidate_count"]
            )
            metadata = {
                "num_detections": 0,
                "num_segments_f2f": 0,
                "num_tracks_after_gap_closing": 0,
                "num_tracks_retained": 0,
                "gaps_closed": 0,
            }
            return TrackingResult(tracks=empty_tracks, metadata=metadata)

        for col in REQUIRED_COLUMNS:
            if col not in detections.columns:
                raise ValueError(f"Detections DataFrame missing required column '{col}'")

        det = detections.sort_values(["frame"]).reset_index(drop=True)
        total_detections = len(det)

        f2f_res = link_consecutive_frames(
            detections=det,
            config=self.config,
            seed=seed,
            lap_solver=self.lap_solver,
        )

        det = det.assign(
            reliability=f2f_res.reliability,
            margin_sigma=f2f_res.margin_sigma,
            candidate_count=f2f_res.candidate_count,
        )
        num_segments_f2f = int(len(np.unique(f2f_res.labels)))

        consolidated_labels = close_trajectory_gaps(
            detections=det,
            segment_labels=f2f_res.labels,
            config=self.config,
            lap_solver=self.lap_solver,
        )
        num_tracks_gap_closed = int(len(np.unique(consolidated_labels)))

        tracks = det.assign(track_id=consolidated_labels)
        track_sizes = tracks.groupby("track_id")["frame"].size()
        retained_ids = track_sizes[track_sizes >= self.config.min_len].index
        tracks = tracks[tracks["track_id"].isin(retained_ids)].copy()

        # Chronological renumbering ordered by first appearance frame
        if not tracks.empty:
            order = tracks.groupby("track_id")["frame"].min().sort_values().index
            id_mapping = {old_id: new_id for new_id, old_id in enumerate(order)}
            tracks["track_id"] = tracks["track_id"].map(id_mapping).astype(np.int32)
            tracks = tracks.sort_values(["track_id", "frame"]).reset_index(drop=True)
            num_retained = int(tracks["track_id"].nunique())
        else:
            num_retained = 0

        metadata = {
            "num_detections": total_detections,
            "num_segments_f2f": num_segments_f2f,
            "num_tracks_after_gap_closing": num_tracks_gap_closed,
            "num_tracks_retained": num_retained,
            "gaps_closed": num_segments_f2f - num_tracks_gap_closed,
        }

        return TrackingResult(tracks=tracks, metadata=metadata)
