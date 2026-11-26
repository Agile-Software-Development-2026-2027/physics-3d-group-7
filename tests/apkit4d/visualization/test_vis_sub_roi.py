import numpy as np
import pandas as pd
import pytest
import pyvista as pv

from apkit4d.core.roi import RegionOfInterest
from apkit4d.visualization.data_mapper import (
    PreparedTrajectories,
    TrajectoryColorMode,
    TrajectoryRenderConfig,
    build_trajectory_polydata,
    create_blob_mesh,
)
from apkit4d.visualization.vis_sub_roi import (
    DEFAULT_BLOB_RGB,
    DEFAULT_OUTSIDE_OPACITY,
    VisSubRoiState,
    apply_vis_sub_roi_to_trajectories,
    build_sub_roi_blobs_polydata,
    build_sub_roi_trajectory_polydata,
    clamp_outside_opacity,
    compute_inside_mask,
    outside_opacity_to_alpha_uint8,
    world_bounds_to_normalized_tex_coords,
)


def _extract_segments(poly: pv.PolyData) -> list[tuple[np.ndarray, np.ndarray, int]]:
    """Return [(p_start, p_end, alpha), ...] for every 2-point line cell in `poly`."""
    lines = np.asarray(poly.lines, dtype=np.int64)
    pts = np.asarray(poly.points, dtype=np.float64)
    alphas = np.asarray(poly.point_data["rgba"][:, 3], dtype=np.uint8)

    segments: list[tuple[np.ndarray, np.ndarray, int]] = []
    idx = 0
    while idx < len(lines):
        count = int(lines[idx])
        verts = lines[idx + 1 : idx + 1 + count]
        for a, b in zip(verts[:-1], verts[1:], strict=False):
            assert alphas[a] == alphas[b]
            segments.append((pts[a], pts[b], int(alphas[a])))
        idx += 1 + count
    return segments


class TestVisSubRoiState:
    def test_defaults_and_outside_alpha(self):
        state = VisSubRoiState()
        assert state.enabled is False
        assert state.bounds is None
        assert state.outside_opacity == pytest.approx(0.01)
        assert pytest.approx(0.01) == DEFAULT_OUTSIDE_OPACITY
        assert state.outside_alpha == 3

    def test_normalizes_bounds_and_clamps_outside_opacity(self):
        state = VisSubRoiState(
            enabled=True,
            bounds=(20.0, 5.0, 30.0, 10.0, 8.0, 2.0),
            outside_opacity=1.5,
        )
        assert state.bounds == (5.0, 20.0, 10.0, 30.0, 2.0, 8.0)
        assert state.outside_opacity == pytest.approx(1.0)
        assert state.outside_alpha == 255

        low_state = VisSubRoiState(
            enabled=True, bounds=(0.0, 10.0, 0.0, 10.0, 0.0, 10.0), outside_opacity=-0.2
        )
        assert low_state.outside_opacity == pytest.approx(0.0)
        assert low_state.outside_alpha == 0

    @pytest.mark.parametrize("bad_val", [float("nan"), float("inf"), float("-inf")])
    def test_non_finite_outside_opacity_raises(self, bad_val: float):
        with pytest.raises(ValueError, match="finite"):
            clamp_outside_opacity(bad_val)
        with pytest.raises(ValueError, match="finite"):
            outside_opacity_to_alpha_uint8(bad_val)

    def test_with_clamped_bounds_respects_non_zero_origin(self):
        grid_bounds = (10.0, 50.0, 20.0, 60.0, 5.0, 25.0)
        state = VisSubRoiState(
            enabled=True,
            bounds=(0.0, 30.0, 40.0, 80.0, 10.0, 15.0),
            outside_opacity=0.05,
        )
        clamped = state.with_clamped_bounds(grid_bounds)
        assert clamped.bounds is not None
        assert clamped.bounds[0] >= 10.0
        assert clamped.bounds[1] <= 50.0
        assert clamped.bounds[2] >= 20.0
        assert clamped.bounds[3] <= 60.0
        assert clamped.bounds[4] >= 5.0
        assert clamped.bounds[5] <= 25.0
        assert clamped.enabled is True
        assert clamped.outside_opacity == pytest.approx(0.05)


class TestSpatialHelpersAndBlobsMask:
    def test_world_bounds_to_normalized_tex_coords_with_offset(self):
        grid_bounds = (10.0, 30.0, 5.0, 25.0, 0.0, 40.0)
        roi_bounds = (15.0, 25.0, 5.0, 15.0, 10.0, 40.0)

        u_min, u_max = world_bounds_to_normalized_tex_coords(roi_bounds, grid_bounds)
        np.testing.assert_allclose(u_min, (0.25, 0.0, 0.25))
        np.testing.assert_allclose(u_max, (0.75, 0.5, 1.0))

    def test_compute_inside_mask_includes_boundary_and_excludes_outside(self):
        bounds = (0.0, 10.0, 0.0, 10.0, 0.0, 10.0)
        pts = np.array(
            [
                [5.0, 5.0, 5.0],
                [0.0, 10.0, 5.0],
                [10.1, 5.0, 5.0],
                [5.0, -0.1, 5.0],
            ],
            dtype=np.float64,
        )
        mask = compute_inside_mask(pts, bounds)
        np.testing.assert_array_equal(mask, np.array([True, True, False, False]))

    def test_roi_filter_blobs_df_does_not_mutate_source(self):
        roi = RegionOfInterest(x_min=0.0, x_max=10.0, y_min=0.0, y_max=10.0, z_min=0.0, z_max=10.0)
        df = pd.DataFrame(
            {
                "frame": [0, 0],
                "label": [1, 2],
                "x_um": [5.0, 20.0],
                "y_um": [5.0, 5.0],
                "z_um": [5.0, 5.0],
            }
        )
        original_copy = df.copy(deep=True)
        filtered = roi.filter_blobs_df(df)
        pd.testing.assert_frame_equal(df, original_copy)
        assert list(filtered["label"]) == [1]


class TestSubRoiBlobsPolydata:
    @staticmethod
    def _sample_blobs_df() -> pd.DataFrame:
        return pd.DataFrame(
            {
                "frame": [0, 0, 0],
                "label": [1, 2, 3],
                "x_um": [2.0, 4.0, 12.0],
                "y_um": [1.0, 4.0, 1.0],
                "z_um": [0.0, 0.0, 0.0],
                "volume_um3": [10.0, 15.0, 20.0],
            }
        )

    def test_empty_or_none_returns_empty_polydata(self):
        assert build_sub_roi_blobs_polydata(None).n_points == 0
        assert build_sub_roi_blobs_polydata(pv.PolyData()).n_points == 0

    @pytest.mark.parametrize(
        "state",
        [
            None,
            VisSubRoiState(enabled=False, bounds=(-4.0, 4.0, -4.0, 4.0, -4.0, 4.0)),
            VisSubRoiState(enabled=True, bounds=None),
        ],
    )
    def test_inactive_state_assigns_full_opacity_red_and_preserves_source(self, state):
        df = self._sample_blobs_df()
        df_before = df.copy(deep=True)
        src_poly = create_blob_mesh(df)
        src_pts_before = np.asarray(src_poly.points).copy()
        src_keys_before = set(src_poly.point_data.keys())

        out = build_sub_roi_blobs_polydata(src_poly, state)

        assert out.n_points == 3
        assert out.active_scalars_name == "rgba"
        expected = np.array([[*DEFAULT_BLOB_RGB, 255]] * 3, dtype=np.uint8)
        np.testing.assert_array_equal(out.point_data["rgba"], expected)
        np.testing.assert_array_equal(out.point_data["label"], np.array([1, 2, 3]))

        # Source DataFrame and PolyData remain completely untouched
        pd.testing.assert_frame_equal(df, df_before)
        assert set(src_poly.point_data.keys()) == src_keys_before
        assert "rgba" not in src_poly.point_data
        np.testing.assert_array_equal(src_poly.points, src_pts_before)

    def test_active_state_assigns_inside_and_outside_alpha_without_sharing_buffers(self):
        src_poly = create_blob_mesh(self._sample_blobs_df())
        state = VisSubRoiState(
            enabled=True,
            bounds=(-4.0, 4.0, -4.0, 4.0, -4.0, 4.0),
            outside_opacity=0.01,
        )

        out = build_sub_roi_blobs_polydata(src_poly, state)
        rgba = out.point_data["rgba"]

        assert rgba.dtype == np.uint8
        assert rgba.shape == (3, 4)
        np.testing.assert_array_equal(rgba[:, :3], np.tile(DEFAULT_BLOB_RGB, (3, 1)))
        # Blob 1 (inside) & Blob 2 (on boundary) -> 255; Blob 3 (outside) -> 3
        np.testing.assert_array_equal(rgba[:, 3], np.array([255, 255, state.outside_alpha], dtype=np.uint8))

        # Mutating display output must not affect source PolyData
        points = np.asarray(out.points)
        points[0, 0] = 999.0
        assert src_poly.points[0, 0] == pytest.approx(2.0)


class TestSubRoiTrajectorySplitting:
    @staticmethod
    def _sample_prepared() -> PreparedTrajectories:
        df = pd.DataFrame(
            {
                "track_id": [1, 1, 2, 2, 3, 3],
                "frame": [0, 2, 0, 1, 0, 1],
                "x_um": [-10.0, 10.0, 0.0, 2.0, -9.0, -6.0],
                "y_um": [0.0, 0.0, 0.0, 0.0, 8.0, 8.0],
                "z_um": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "t_s": [0.0, 2.0, 0.0, 1.0, 0.0, 1.0],
            }
        )
        return PreparedTrajectories.from_dataframe(df)

    @staticmethod
    def _make_line_poly(
        p0: tuple[float, float, float],
        p1: tuple[float, float, float],
        rgb0: tuple[int, int, int] = (20, 120, 240),
        rgb1: tuple[int, int, int] = (20, 120, 240),
    ) -> pv.PolyData:
        poly = pv.PolyData(
            np.array([p0, p1], dtype=np.float32),
            lines=np.array([2, 0, 1], dtype=np.int64),
        )
        poly.point_data["rgb"] = np.array([rgb0, rgb1], dtype=np.uint8)
        return poly

    @pytest.mark.parametrize(
        "state",
        [
            None,
            VisSubRoiState(enabled=False, bounds=(-4.0, 4.0, -4.0, 4.0, -4.0, 4.0), outside_opacity=0.01),
            VisSubRoiState(enabled=True, bounds=None, outside_opacity=0.01),
        ],
    )
    def test_inactive_reproduces_original_geometry_and_exact_rgb_without_mutation(self, state):
        prepared = self._sample_prepared()
        pts_before = prepared.points_um.copy()
        frames_before = prepared.frames.copy()
        tids_before = prepared.track_ids.copy()
        speeds_before = prepared.speeds.copy()

        cfg = TrajectoryRenderConfig(
            color_mode=TrajectoryColorMode.SPEED,
            colormap="viridis",
            tail_length=2,
        )
        base_poly = build_trajectory_polydata(prepared, current_frame=2, config=cfg)
        base_pts_before = np.asarray(base_poly.points).copy()
        base_rgb_before = np.asarray(base_poly.point_data["rgb"]).copy()

        out_poly = apply_vis_sub_roi_to_trajectories(base_poly, state)

        assert out_poly.n_points == base_poly.n_points
        assert out_poly.n_cells == base_poly.n_cells
        assert out_poly.active_scalars_name == "rgba"
        np.testing.assert_array_equal(out_poly.lines, base_poly.lines)
        np.testing.assert_array_equal(out_poly.points, base_pts_before)
        np.testing.assert_array_equal(out_poly.point_data["rgba"][:, :3], base_rgb_before)
        np.testing.assert_array_equal(
            out_poly.point_data["rgba"][:, 3], np.full(out_poly.n_points, 255, dtype=np.uint8)
        )

        # Neither base_poly nor prepared is mutated
        assert "rgba" not in base_poly.point_data
        np.testing.assert_array_equal(prepared.points_um, pts_before)
        np.testing.assert_array_equal(prepared.frames, frames_before)
        np.testing.assert_array_equal(prepared.track_ids, tids_before)
        np.testing.assert_array_equal(prepared.speeds, speeds_before)

    @pytest.mark.parametrize(
        ("color_mode", "colormap", "tail_length"),
        [
            (TrajectoryColorMode.SPEED, "viridis", -1),
            (TrajectoryColorMode.SPEED, "plasma", 1),
            (TrajectoryColorMode.TRACK_ID, "turbo", -1),
        ],
    )
    def test_preserves_exact_rgb_for_color_mode_colormap_and_tail_length(
        self, color_mode, colormap, tail_length
    ):
        df = pd.DataFrame(
            {
                "track_id": [1, 1, 1, 2, 2, 2],
                "frame": [0, 1, 2, 0, 1, 2],
                "x_um": [0.0, 1.0, 2.0, -9.0, -8.0, -7.0],
                "y_um": [0.0, 0.0, 0.0, 8.0, 8.0, 8.0],
                "z_um": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
                "t_s": [0.0, 1.0, 2.0, 0.0, 1.0, 2.0],
            }
        )
        prepared = PreparedTrajectories.from_dataframe(df)
        cfg = TrajectoryRenderConfig(color_mode=color_mode, colormap=colormap, tail_length=tail_length)
        base_poly = build_trajectory_polydata(prepared, current_frame=2, config=cfg)

        state = VisSubRoiState(enabled=True, bounds=(-4.0, 4.0, -4.0, 4.0, -4.0, 4.0), outside_opacity=0.2)
        out_poly = build_sub_roi_trajectory_polydata(prepared, current_frame=2, config=cfg, state=state)

        # Track 1 is fully internal, Track 2 is fully external -> exact vertex RGB preserved on every segment
        assert out_poly.n_cells == (4 if tail_length == -1 else 2)
        for tid, expected_alpha in ((1, 255), (2, state.outside_alpha)):
            base_mask = base_poly.point_data["track_id"] == tid
            out_mask = out_poly.point_data["track_id"] == tid
            expected_rgbs = set(map(tuple, base_poly.point_data["rgb"][base_mask].tolist()))
            actual_rgbs = set(map(tuple, out_poly.point_data["rgba"][out_mask, :3].tolist()))
            assert actual_rgbs == expected_rgbs
            assert np.all(out_poly.point_data["rgba"][out_mask, 3] == expected_alpha)

    def test_crossing_track_splits_at_aabb_faces_and_assigns_inside_outside_alpha(self):
        prepared = self._sample_prepared()
        cfg = TrajectoryRenderConfig(color_mode=TrajectoryColorMode.SPEED, colormap="turbo")
        state = VisSubRoiState(enabled=True, bounds=(-4.0, 4.0, -4.0, 4.0, -4.0, 4.0), outside_opacity=0.01)

        poly = build_sub_roi_trajectory_polydata(prepared, current_frame=2, config=cfg, state=state)
        assert poly.n_points > 0
        assert poly.n_cells > 0
        assert poly.active_scalars_name == "rgba"

        # Track 1 crosses x = -4.0 (t=0.3) and x = +4.0 (t=0.7), so frame values 0.6 and 1.4 appear
        frames = poly.point_data["frame"]
        assert np.any(np.isclose(frames, 0.6, atol=1e-3))
        assert np.any(np.isclose(frames, 1.4, atol=1e-3))

        # Track 2 is inside (-4..4); Track 3 is outside (x=-9..-6, y=8)
        tids = poly.point_data["track_id"]
        alphas = poly.point_data["rgba"][:, 3]

        track2_alphas = alphas[tids == 2]
        track3_alphas = alphas[tids == 3]
        assert len(track2_alphas) > 0
        assert len(track3_alphas) > 0
        assert np.all(track2_alphas == 255)
        assert np.all(track3_alphas == state.outside_alpha)

    def test_aabb_edge_cases_produce_no_degenerate_or_duplicate_segments(self):
        bounds = (-4.0, 4.0, -4.0, 4.0, -4.0, 4.0)
        state = VisSubRoiState(enabled=True, bounds=bounds, outside_opacity=0.1)
        out_alpha = state.outside_alpha

        cases = [
            # (description, p0, p1, expected_alphas_in_order)
            ("fully_internal", (-2.0, 1.0, 0.0), (3.0, -1.0, 2.0), [255]),
            ("fully_external", (-10.0, 8.0, 0.0), (-6.0, 8.0, 0.0), [out_alpha]),
            ("non_intersecting_crosses_infinite_planes", (-10.0, 8.0, 0.0), (10.0, 8.0, 0.0), [out_alpha]),
            ("non_intersecting_diagonal_near_corner", (0.0, 10.0, 0.0), (10.0, 0.0, 0.0), [out_alpha]),
            ("crossing_single_face_outward", (0.0, 0.0, 0.0), (10.0, 0.0, 0.0), [255, out_alpha]),
            ("crossing_two_faces", (-10.0, 0.0, 0.0), (10.0, 0.0, 0.0), [out_alpha, 255, out_alpha]),
            ("boundary_lying_on_face", (-4.0, 4.0, 0.0), (4.0, 4.0, 0.0), [255]),
            ("boundary_grazing_single_corner", (0.0, 8.0, 0.0), (8.0, 0.0, 0.0), [out_alpha]),
            ("boundary_start_on_face_outward", (4.0, 0.0, 0.0), (10.0, 0.0, 0.0), [out_alpha]),
            ("boundary_start_on_face_inward", (-4.0, 0.0, 0.0), (2.0, 0.0, 0.0), [255]),
        ]

        for label, p0, p1, expected_alphas in cases:
            src = self._make_line_poly(p0, p1, rgb0=(10, 200, 30), rgb1=(10, 200, 30))
            out = apply_vis_sub_roi_to_trajectories(src, state)
            segs = _extract_segments(out)

            assert [alpha for _, _, alpha in segs] == expected_alphas, f"Failed case: {label}"

            # Verify no degenerate (zero-length) or duplicate segments and exact RGB preservation
            seen: set[tuple[tuple[float, ...], tuple[float, ...]]] = set()
            for a, b, _ in segs:
                assert np.linalg.norm(b - a) > 1e-6, f"Degenerate segment in case: {label}"
                key = (tuple(np.round(a, 5)), tuple(np.round(b, 5)))
                assert key not in seen, f"Duplicate segment in case: {label}"
                seen.add(key)

            np.testing.assert_array_equal(
                out.point_data["rgba"][:, :3],
                np.tile(np.array([10, 200, 30], dtype=np.uint8), (out.n_points, 1)),
            )
