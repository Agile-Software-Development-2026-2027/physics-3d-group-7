"""Unit tests for diagnostic visualization rendering."""

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from apkit4d.analysis.diagnostics import render_diagnostics_figure
from apkit4d.core.models import TrackingConfig


class TestRenderDiagnosticsFigure:
    def test_render_with_complete_data_and_time(self) -> None:
        """Verify rendering a 6-panel diagnostics figure with full data and sampling interval dt_s."""
        # Create 2 synthetic tracks with 25 points each
        rows = []
        for pid in [0, 1]:
            for f in range(25):
                rows.append(
                    {
                        "track_id": pid,
                        "frame": f,
                        "z_um": 10.0 * pid + float(f),
                        "y_um": 5.0 * pid,
                        "x_um": 2.0 * float(f),
                        "reliability": 0.95,
                        "margin_sigma": 4.5,
                        "candidate_count": 1,
                    }
                )
        tracks_df = pd.DataFrame(rows)

        stats_df = pd.DataFrame(
            {
                "track_id": [0, 1],
                "n_points": [25, 25],
                "median_step_um": [2.2, 2.2],
                "median_turn_deg": [0.0, 0.0],
                "frac_turn_gt_120": [0.0, 0.0],
                "min_margin_sigma": [4.5, 2.5],
            }
        )

        info = {"num_tracks_retained": 2}
        config = TrackingConfig(max_dist_um=15.0, max_gap=2)

        fig = render_diagnostics_figure(
            tracks=tracks_df,
            stats=stats_df,
            info=info,
            config=config,
            name="Experiment-Test",
            dt_s=0.05,
        )

        assert len(fig.axes) == 6
        assert "Experiment-Test" in fig._suptitle.get_text()
        assert "2 tracks" in fig._suptitle.get_text()

        # Check English titles and Greek letter translations across panels
        assert "A - track length" in fig.axes[0].get_title()
        assert "points per track" in fig.axes[0].get_xlabel()
        assert "number of tracks" in fig.axes[0].get_ylabel()

        assert "B - active tracks" in fig.axes[1].get_title()
        assert "active tracks" in fig.axes[1].get_ylabel()

        assert "θ(theta)" in fig.axes[2].get_ylabel()
        assert "direction autocorrelation" in fig.axes[2].get_title()

        assert "C - swimming velocity" in fig.axes[3].get_title()
        assert "median velocity per track" in fig.axes[3].get_xlabel()

        assert "D - direction changes" in fig.axes[4].get_title()
        assert "turn angle between successive steps" in fig.axes[4].get_xlabel()

        assert "σ(sigma)" in fig.axes[5].get_xlabel()
        assert "σ(sigma)" in fig.axes[5].get_title()
        assert "connection contention" in fig.axes[5].get_title()

        plt.close(fig)

    def test_render_without_dt_s(self) -> None:
        """Verify fallback labels when temporal interval dt_s is not provided."""
        tracks_df = pd.DataFrame(
            {
                "track_id": [0, 0, 0],
                "frame": [0, 1, 2],
                "z_um": [0.0, 1.0, 2.0],
                "y_um": [0.0, 0.0, 0.0],
                "x_um": [0.0, 0.0, 0.0],
            }
        )
        stats_df = pd.DataFrame(
            {
                "track_id": [0],
                "n_points": [3],
                "median_step_um": [1.0],
                "median_turn_deg": [0.0],
                "frac_turn_gt_120": [0.0],
                "min_margin_sigma": [np.inf],
            }
        )
        info = {"num_tracks_retained": 1}
        config = TrackingConfig()

        fig = render_diagnostics_figure(
            tracks=tracks_df,
            stats=stats_df,
            info=info,
            config=config,
            dt_s=None,
        )

        assert len(fig.axes) == 6
        # Panel C (axes[1, 0], flattened index 3) should have units in um, not um/s
        assert "median step size (µm)" in fig.axes[3].get_xlabel()
        plt.close(fig)

    def test_render_empty_data(self) -> None:
        """Verify robust figure rendering on empty DataFrames without exceptions."""
        empty_tracks = pd.DataFrame()
        empty_stats = pd.DataFrame()
        info = {"num_tracks_retained": 0}
        config = TrackingConfig()

        fig = render_diagnostics_figure(
            tracks=empty_tracks,
            stats=empty_stats,
            info=info,
            config=config,
            name="Empty-Test",
        )

        assert len(fig.axes) == 6
        assert "0 tracks" in fig._suptitle.get_text()
        assert "A - no tracks available" in fig.axes[0].get_title()
        assert "B - no frame data available" in fig.axes[1].get_title()
        assert "C - velocity not available" in fig.axes[3].get_title()
        assert "D - turn angles not available" in fig.axes[4].get_title()
        assert "F - no margin data available" in fig.axes[5].get_title()
        plt.close(fig)
