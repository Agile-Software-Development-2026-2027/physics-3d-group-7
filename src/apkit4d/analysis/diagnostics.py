"""
Diagnostic visualization dashboard for particle tracking and motility analysis.

This module renders a 6-panel Matplotlib dashboard evaluating tracking quality, active track
counts, velocity distributions, directional autocorrelation, and assignment ambiguities.
"""

from typing import Any

import matplotlib.figure
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apkit4d.analysis.motility import compute_direction_acf
from apkit4d.core.models import TrackingConfig


def render_diagnostics_figure(
    tracks: pd.DataFrame,
    stats: pd.DataFrame,
    info: dict[str, Any],
    config: TrackingConfig,
    name: str = "",
    dt_s: float | None = None,
) -> matplotlib.figure.Figure:
    """Render a 6-panel diagnostic figure evaluating particle linking quality.

    Panels:
        - 1: Track length distribution (log scale).
        - 2: Active tracks per frame across time.
        - 3: Median velocity (or step size) distribution.
        - 4: Turn angle distribution and reversal frequency.
        - 5: Direction autocorrelation function <cos θ(theta)> vs lag.
        - 6: Ambiguity margin distribution (σ(sigma) of second choice).

    Args:
        tracks: Reconstructed trajectories DataFrame containing 'track_id' and 'frame'.
        stats: Trajectory summary statistics DataFrame from `compute_track_statistics`.
        info: Summary dictionary from tracking (contains 'num_tracks_retained').
        config: Tracking configuration parameters.
        name: Name or dataset identifier displayed in the figure title.
        dt_s: Physical sampling interval between frames in seconds.

    Returns:
        matplotlib.figure.Figure instance containing the 6 diagnostic panels.

    RefactorNote:
        Equivalent of `make_diagnostics` from legacy.
    """
    num_retained = info.get("num_tracks_retained", 0)

    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle(
        f"{name} - linking LAP  (gate {config.max_dist_um:g} µm, gap ≤ {config.max_gap}, "
        f"{num_retained} tracks)",
        fontsize=11,
    )

    # Panel 1 (axes[0, 0]): Track length distribution
    ax_a = axes[0, 0]
    if not stats.empty and "n_points" in stats.columns and stats["n_points"].notna().any():
        max_pts = int(stats["n_points"].max())
        ax_a.hist(
            stats["n_points"],
            bins=range(1, max_pts + 2),
            color="#00838f",
        )
        ax_a.set(
            xlabel="points per track",
            ylabel="number of tracks",
            yscale="log",
            title=f"A - track length (median {stats['n_points'].median():.0f})",
        )
    else:
        ax_a.set(title="A - no tracks available")
    ax_a.grid(alpha=0.3)

    # Panel 2 (axes[0, 1]): Active tracks per frame across time
    ax_b = axes[0, 1]
    if not tracks.empty and "track_id" in tracks.columns and "frame" in tracks.columns:
        per_frame = tracks.groupby("frame")["track_id"].nunique()
        ax_b.plot(per_frame.index, per_frame.values, lw=1, color="#1e88e5")
        ax_b.set(xlabel="frame", ylabel="active tracks", title="B - active tracks per frame")
    else:
        ax_b.set(title="B - no frame data available")
    ax_b.grid(alpha=0.3)

    # Panel 3 (axes[1, 0]): Median velocity (or step size) distribution
    ax_c = axes[1, 0]
    if not stats.empty and "median_step_um" in stats.columns:
        step = stats["median_step_um"].dropna()
        speed = step / dt_s if dt_s else step
        if len(speed) > 0:
            ax_c.hist(speed, bins=60, color="#8e24aa")
        ax_c.set(
            xlabel="median velocity per track (µm/s)" if dt_s else "median step size (µm)",
            ylabel="number of tracks",
            title="C - swimming velocity",
        )
    else:
        ax_c.set(title="C - velocity not available")
    ax_c.grid(alpha=0.3)

    # Panel 4 (axes[0, 2]): Direction autocorrelation function <cos θ(theta)> vs lag
    ax_e = axes[0, 2]
    lags, acf = compute_direction_acf(tracks)
    if len(lags) > 0:
        x_vals = lags * dt_s if dt_s else lags
        ax_e.plot(x_vals, acf, "o-", color="#43a047")
        ax_e.axhline(0, color="gray", lw=0.8)
    ax_e.set(
        xlabel="lag (s)" if dt_s else "lag (frame)",
        ylabel="⟨cos θ(theta)⟩",
        title="E - direction autocorrelation\n(oscillation = helical swimming)",
    )
    ax_e.grid(alpha=0.3)

    # Panel 5 (axes[1, 2]): Ambiguity margin distribution (σ(sigma) of second choice)
    ax_f = axes[1, 2]
    if "min_margin_sigma" in stats.columns and not stats.empty:
        marg = stats["min_margin_sigma"].replace(np.inf, np.nan).dropna()
        if len(marg) > 0:
            ax_f.hist(np.clip(marg, 0, 40), bins=40, color="#5e35b1")
            ax_f.axvline(3, color="red", ls="--", lw=1)
            contested_pct = 100.0 * (marg < 3).mean()
            never_contested_pct = 100.0 * (stats["min_margin_sigma"] == np.inf).mean()
            ax_f.set(
                xlabel="minimum margin on second choice (σ(sigma) of prediction)",
                ylabel="number of tracks",
                title=(
                    f"F - connection contention\n"
                    f"below 3σ(sigma): {contested_pct:.1f}% - never contested: {never_contested_pct:.0f}%"
                ),
            )
        else:
            ax_f.set(title="F - no contested connections")
    else:
        ax_f.set(title="F - no margin data available")
    ax_f.grid(alpha=0.3)

    # Panel 6 (axes[1, 1]): Turn angles distribution
    ax_d = axes[1, 1]
    if not stats.empty and "median_turn_deg" in stats.columns:
        turn = stats["median_turn_deg"].dropna()
        if len(turn) > 0:
            ax_d.hist(turn, bins=36, range=(0, 180), color="#fb8c00")
            ax_d.axvline(120, color="red", ls="--", lw=1)
        frac_val = (
            float(stats["frac_turn_gt_120"].mean())
            if "frac_turn_gt_120" in stats.columns and stats["frac_turn_gt_120"].notna().any()
            else 0.0
        )
        ax_d.set(
            xlabel="turn angle between successive steps (°)",
            ylabel="number of tracks",
            title=f"D - direction changes  (steps over 120°: {100.0 * frac_val:.1f}%)",
        )
    else:
        ax_d.set(title="D - turn angles not available")
    ax_d.grid(alpha=0.3)

    fig.tight_layout()
    return fig
