"""
Unit tests for ParticleLinker coordinator.

RefactorNote:
    While all tests are good `test_linker_end_to_end_straight_swimmers` and `test_linker_filters_short_tracks`
    where the worst to write and I do not really liek them, I'd expect for tests taht tests such sensibel data
    to have whay more cases to test from, BUT we're still not ready to extract data from real experiments, so
    for now this will have to do.

TODO: add more testcases with parametrized tests to include a wired variety of cases
"""

import pandas as pd
import pytest

from apkit4d.core.models import TrackingConfig
from apkit4d.tracking.linker import ParticleLinker


class TestParticleLinker:
    def test_linker_empty_detections(self) -> None:
        """Verify linker on empty input DataFrame."""
        linker = ParticleLinker()
        df = pd.DataFrame(columns=["frame", "z_um", "y_um", "x_um"])
        res = linker.link(df)
        assert res.tracks.empty
        assert res.metadata["num_detections"] == 0
        assert res.metadata["num_tracks_retained"] == 0

    def test_linker_missing_required_column(self) -> None:
        """Verify ValueError when required coordinate column is missing."""
        linker = ParticleLinker()
        df = pd.DataFrame({"frame": [0, 1], "z_um": [1.0, 2.0], "y_um": [1.0, 2.0]})
        with pytest.raises(ValueError, match="missing required column 'x_um'"):
            linker.link(df)

    def test_linker_end_to_end_straight_swimmers(self) -> None:
        """Verify end-to-end linking on two straight swimmers over 5 frames."""
        cfg = TrackingConfig(max_dist_um=15.0, min_len=3, mc_resamples=10)
        linker = ParticleLinker(config=cfg)

        rows = []
        # Swimmer 0 starts at (10, 0, 0), moves +2 um/frame along z
        # Swimmer 1 starts at (100, 0, 0), moves -1 um/frame along y
        for f in range(5):
            rows.append({"frame": f, "z_um": 10.0 + 2.0 * f, "y_um": 0.0, "x_um": 0.0})
            rows.append({"frame": f, "z_um": 100.0, "y_um": -1.0 * f, "x_um": 0.0})

        df = pd.DataFrame(rows)
        # Shuffle order to add chaos to the equation
        df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)

        result = linker.link(df)
        tracks = result.tracks

        assert result.metadata["num_detections"] == 10
        assert result.metadata["num_tracks_retained"] == 2
        assert tracks["track_id"].nunique() == 2

        counts = tracks.groupby("track_id").size()
        assert counts.iloc[0] == 5
        assert counts.iloc[1] == 5

        assert "reliability" in tracks.columns
        assert "margin_sigma" in tracks.columns
        assert "candidate_count" in tracks.columns

        # Verify stats computation is automatically triggered
        assert not result.stats.empty
        assert len(result.stats) == 2
        assert "track_id" in result.stats.columns
        assert "median_step_um" in result.stats.columns

    def test_linker_computes_diagnostics_figure(self) -> None:
        """Verify that linker generates a valid diagnostics figure when requested."""
        import matplotlib.pyplot as plt

        cfg = TrackingConfig(max_dist_um=15.0, min_len=2)
        linker = ParticleLinker(config=cfg)

        rows = []
        for f in range(3):
            rows.append({"frame": f, "z_um": 10.0 + f, "y_um": 0.0, "x_um": 0.0, "t_s": 0.1 * f})

        df = pd.DataFrame(rows)
        res = linker.link(df, compute_diagnostics=True, dataset_name="Sample_Exp", dt_s=0.1)

        assert res.diagnostics_figure is not None
        assert len(res.diagnostics_figure.axes) == 6
        plt.close(res.diagnostics_figure)

    def test_linker_filters_short_tracks(self) -> None:
        """Verify that tracks with points < min_len are pruned."""
        cfg = TrackingConfig(max_dist_um=10.0, min_len=4)
        linker = ParticleLinker(config=cfg)

        rows = []
        for f in range(5):
            rows.append({"frame": f, "z_um": float(f), "y_um": 0.0, "x_um": 0.0})
        rows.append({"frame": 0, "z_um": 200.0, "y_um": 0.0, "x_um": 0.0})
        rows.append({"frame": 1, "z_um": 201.0, "y_um": 0.0, "x_um": 0.0})

        df = pd.DataFrame(rows)
        result = linker.link(df)

        assert result.metadata["num_tracks_retained"] == 1
        assert result.tracks["track_id"].nunique() == 1
        assert len(result.tracks) == 5

        strict_linker = ParticleLinker(config=TrackingConfig(min_len=10))
        strict_res = strict_linker.link(df)
        assert strict_res.metadata["num_tracks_retained"] == 0
        assert strict_res.tracks.empty

    def test_linker_max_speed_scales_frame_to_frame_gate_when_dt_provided(self) -> None:
        """Verify max_speed_um_s scales max_dist_um when dt_s is provided."""
        # Particle steps 1.5 um/frame; with dt_s=0.1s, physical speed is 15 um/s.
        df = pd.DataFrame([{"frame": f, "z_um": 0.0, "y_um": 0.0, "x_um": 1.5 * f} for f in range(5)])

        fast_cfg = TrackingConfig(max_speed_um_s=20.0, min_len=4, mc_resamples=0)
        fast_res = ParticleLinker(config=fast_cfg).link(df, dt_s=0.1)
        assert fast_res.metadata["max_dist_um"] == pytest.approx(2.0)
        assert fast_res.metadata["gap_dist_um"] == pytest.approx(2.5)
        assert fast_res.metadata["num_tracks_retained"] == 1

        slow_cfg = TrackingConfig(max_speed_um_s=10.0, min_len=4, mc_resamples=0)
        slow_res = ParticleLinker(config=slow_cfg).link(df, dt_s=0.1)
        assert slow_res.metadata["max_dist_um"] == pytest.approx(1.0)
        assert slow_res.metadata["gap_dist_um"] == pytest.approx(1.25)
        assert slow_res.metadata["num_tracks_retained"] == 0

    def test_linker_max_speed_scales_gap_closing_gate_when_dt_provided(self) -> None:
        """Verify max_speed_um_s scales gap_dist_um when dt_s is provided."""
        # Two 3-point segments separated by gap=2 frames (frame 2 -> 4) with a 3.0 um lateral jump.
        seg_a = [{"frame": f, "z_um": 0.0, "y_um": 0.0, "x_um": 0.5 * f} for f in (0, 1, 2)]
        seg_b = [{"frame": f, "z_um": 0.0, "y_um": 3.0, "x_um": 0.5 * f} for f in (4, 5, 6)]
        df = pd.DataFrame(seg_a + seg_b)

        # dt_s=0.1, max_speed=10 -> max_dist=1.0 (links each segment), gap_dist=1.25 -> 2*1.25=2.5 < 3.0
        tight_cfg = TrackingConfig(max_speed_um_s=10.0, max_gap=2, min_len=5, mc_resamples=0)
        tight_res = ParticleLinker(config=tight_cfg).link(df, dt_s=0.1)
        assert tight_res.metadata["num_tracks_retained"] == 0

        # dt_s=0.1, max_speed=20 -> max_dist=2.0, gap_dist=2.5 -> 2*2.5=5.0 >= 3.0 (bridges gap!)
        wide_cfg = TrackingConfig(max_speed_um_s=20.0, max_gap=2, min_len=5, mc_resamples=0)
        wide_res = ParticleLinker(config=wide_cfg).link(df, dt_s=0.1)
        assert wide_res.metadata["num_tracks_retained"] == 1
        assert wide_res.metadata["gaps_closed"] == 1
