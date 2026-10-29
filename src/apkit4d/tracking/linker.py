"""Master ParticleLinker engine coordinating multi-frame trajectory tracking.

This module provides the main entry point for tracking detected particles across time.
It coordinates frame-to-frame LAP matching, gap closing, track length filtering,
and canonical track ID ordering.

RefactorNote:
    Equivalent of `run_link` from legacy `link.py` (lines 306-328).
"""

from dataclasses import dataclass, field
from typing import Any

import matplotlib.figure
import numpy as np
import pandas as pd

from apkit4d.analysis.diagnostics import render_diagnostics_figure
from apkit4d.analysis.metrics import STATS_COLUMNS, compute_track_statistics
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
    stats: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=STATS_COLUMNS))
    diagnostics_figure: matplotlib.figure.Figure | None = None


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

    def link(
        self,
        detections: pd.DataFrame,
        seed: int = 0,
        compute_stats: bool = True,
        compute_diagnostics: bool = False,
        dataset_name: str = "",
        dt_s: float | None = None,
    ) -> TrackingResult:
        """
        Link particle detections across frames into continuous trajectories.

        Args:
            detections: Input DataFrame with at least ['frame', 'z_um', 'y_um', 'x_um'].
            seed: Random seed for Monte Carlo stability perturbations.
            compute_stats: Whether to compute per-track summary metrics (default True,
                matching legacy run_link).
            compute_diagnostics: Whether to generate the 6-panel diagnostics figure (default False).
            dataset_name: Dataset name displayed on the diagnostics figure title.
            dt_s: Time step in seconds between successive frames for speed scaling.

        Returns:
            TrackingResult with tracked DataFrame, summary metadata, trajectory statistics,
            and optional figure.

        RefactorNote:
            Equivalent of `run_link` from legacy `link.py` (lines 306-328).
        """
        if detections.empty:
            empty_tracks = pd.DataFrame(
                columns=list(detections.columns)
                + ["track_id", "reliability", "margin_sigma", "candidate_count"]
            )
            empty_stats = pd.DataFrame(columns=STATS_COLUMNS)
            metadata = {
                "num_detections": 0,
                "num_segments_f2f": 0,
                "num_tracks_after_gap_closing": 0,
                "num_tracks_retained": 0,
                "gaps_closed": 0,
            }
            return TrackingResult(
                tracks=empty_tracks,
                metadata=metadata,
                stats=empty_stats,
                diagnostics_figure=None,
            )

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

        stats = compute_track_statistics(tracks) if compute_stats else pd.DataFrame(columns=STATS_COLUMNS)
        diagnostics_fig = None
        if compute_diagnostics and not tracks.empty:
            diagnostics_fig = render_diagnostics_figure(
                tracks=tracks,
                stats=stats,
                info=metadata,
                config=self.config,
                name=dataset_name,
                dt_s=dt_s,
            )

        return TrackingResult(
            tracks=tracks,
            metadata=metadata,
            stats=stats,
            diagnostics_figure=diagnostics_fig,
        )
