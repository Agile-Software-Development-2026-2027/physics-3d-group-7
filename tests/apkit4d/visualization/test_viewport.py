import numpy as np
import pytest
import pyvista as pv

from apkit4d.visualization.viewport import Viewport


def make_grid(n: int = 5) -> pv.ImageData:
    grid = pv.ImageData(dimensions=(n, n, n))
    grid.point_data["values"] = np.random.rand(grid.n_points)
    return grid


def make_poly(offset: float = 0.0) -> pv.PolyData:
    return pv.PolyData(np.array([[0, 0, 0], [1, 1, 1]], dtype=float) + offset)


def dist(a, b):
    return np.linalg.norm(np.array(a, dtype=float) - np.array(b, dtype=float))


def step(viewport, direction, **overrides):
    kwargs = dict(
        position=(0, 0, 10),
        focal_point=(0, 0, 0),
        target_point=(1, 0, 0),
        volume_center=(0, 0, 0),
        direction=direction,
        zoom_factor=0.2,
        min_dist=1.0,
        max_dist=100.0,
        bounds=None,
    )
    kwargs.update(overrides)

    for key in ("position", "focal_point", "target_point", "volume_center"):
        if kwargs[key] is not None:
            kwargs[key] = np.asarray(kwargs[key], dtype=float)

    return viewport.compute_local_zoom_step(**kwargs)


@pytest.fixture
def viewport(qtbot):
    vp = Viewport()
    qtbot.addWidget(vp)
    yield vp
    vp.plotter.close()


FAR_CAMERA = [(100, 100, 100), (0, 0, 0), (0, 0, 1)]


class TestViewport:
    def test_viewport_initialization(self, viewport):
        assert viewport.plotter is not None
        assert viewport.main_layout is not None
        assert viewport.main_layout.count() == 1

    def test_show_volume_adds_actor(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        assert "volume" in viewport.plotter.actors

    def test_show_volume_with_none_does_nothing(self, viewport):
        viewport.show_volume(None)
        assert "volume" not in viewport.plotter.actors

    def test_second_call_to_show_volume_replaces_actor(self, viewport):
        viewport.show_volume(make_grid(5), reset_camera=False)
        initial_actors = len(viewport.plotter.actors)

        viewport.show_volume(make_grid(10), reset_camera=False)

        assert len(viewport.plotter.actors) == initial_actors

    def test_reset_camera_true_moves_camera(self, viewport):
        viewport.plotter.camera_position = FAR_CAMERA
        before = viewport.plotter.camera_position

        viewport.show_volume(make_grid(), reset_camera=True)

        assert viewport.plotter.camera_position != before

    def test_reset_camera_false_keeps_camera(self, viewport):
        viewport.plotter.camera_position = FAR_CAMERA
        before = viewport.plotter.camera_position

        viewport.show_volume(make_grid(), reset_camera=False)

        assert viewport.plotter.camera_position == before

    def test_show_blobs_adds_actor(self, viewport):
        viewport.show_blobs(make_poly())
        assert "blobs" in viewport.plotter.actors

    def test_show_blobs_with_empty_polydata_does_nothing(self, viewport):
        viewport.show_blobs(pv.PolyData())
        assert "blobs" not in viewport.plotter.actors

    def test_show_blobs_with_none_does_nothing(self, viewport):
        viewport.show_blobs(None)
        assert "blobs" not in viewport.plotter.actors

    def test_second_call_to_show_blobs_replaces_actor(self, viewport):
        viewport.show_blobs(make_poly(0))
        initial_actors = len(viewport.plotter.actors)

        viewport.show_blobs(make_poly(2))

        assert len(viewport.plotter.actors) == initial_actors

    def test_blobs_do_not_change_camera_position(self, viewport):
        viewport.plotter.camera_position = FAR_CAMERA
        before = viewport.plotter.camera_position

        viewport.show_blobs(make_poly())
        viewport.show_blobs(make_poly())

        assert viewport.plotter.camera_position == before

    def test_clear_removes_volume(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        viewport.clear()
        assert "volume" not in viewport.plotter.actors

    def test_clear_removes_blobs(self, viewport):
        viewport.show_blobs(make_poly())
        viewport.clear()
        assert "blobs" not in viewport.plotter.actors

    def test_clear_removes_volume_and_blobs(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        viewport.show_blobs(make_poly())

        viewport.clear()

        assert "volume" not in viewport.plotter.actors
        assert "blobs" not in viewport.plotter.actors

    def test_clear_with_no_actors(self, viewport):
        viewport.clear()  # should not raise any exceptions

    def test_clear_multiple_times(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        viewport.clear()
        viewport.clear()
        assert "volume" not in viewport.plotter.actors

    def test_can_show_again_after_clear(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        viewport.clear()
        viewport.show_volume(make_grid(), reset_camera=False)
        assert "volume" in viewport.plotter.actors

    def test_clamp_too_close(self, viewport):
        pos = viewport.clamp_camera_position([0, 0, 1], [0, 0, 0], 5.0, 20.0)
        assert np.allclose(pos, [0, 0, 5])

    def test_clamp_too_far(self, viewport):
        pos = viewport.clamp_camera_position([0, 0, 100], [0, 0, 0], 5.0, 20.0)
        assert np.allclose(pos, [0, 0, 20])

    def test_clamp_inside_range(self, viewport):
        pos = viewport.clamp_camera_position([0, 0, 10], [0, 0, 0], 5.0, 20.0)
        assert np.allclose(pos, [0, 0, 10])

    def test_clamp_with_distance_equal_to_zero(self, viewport):
        pos = viewport.clamp_camera_position([0, 0, 10], [0, 0, 10], 5.0, 20.0)
        assert np.allclose(pos, [0, 0, 10])

    def test_clamp_points_with_bounds_none(self, viewport):
        pos = viewport.clamp_point_to_bounds([0, 0, 0], None)
        assert np.allclose(pos, [0, 0, 0])

    def test_clamp_points_bounds_not_six(self, viewport):
        pos = viewport.clamp_point_to_bounds([0, 0, 0], (-1, 1, -1, 1))
        assert np.allclose(pos, [0, 0, 0])


class TestComputeLocalZoomStep:
    def test_distance_is_zero(self, viewport):
        new_pos, new_focal = step(viewport, 1, position=(0, 0, 0), focal_point=(0, 0, 0))
        assert np.allclose(new_pos, [0, 0, 0])
        assert np.allclose(new_focal, [0, 0, 0])

    def test_distance_is_divided_by_one_plus_step(self, viewport):
        new_pos, new_focal = step(viewport, 1, zoom_factor=0.25)
        assert dist(new_pos, new_focal) == pytest.approx(10 / 1.25)

    def test_distance_never_below_min_dist(self, viewport):
        new_pos, new_focal = step(viewport, 1, min_dist=9.5, zoom_factor=0.35)
        assert dist(new_pos, new_focal) == pytest.approx(9.5)

    def test_already_at_min_dist_keeps_distance_and_focal(self, viewport):
        new_pos, new_focal = step(
            viewport,
            1,
            position=(0, 0, 5),
            min_dist=5.0,
            target_point=(3, 0, 0),
        )
        assert np.allclose(new_focal, [0, 0, 0])
        assert np.allclose(new_pos, [0, 0, 5])

    def test_focal_moves_towards_target_by_effective_alpha(self, viewport):
        # alpha = (dist - new_dist) / dist = step / (1 + step)
        s = 0.2
        alpha = s / (1 + s)
        _, new_focal = step(viewport, 1, zoom_factor=s, target_point=(6, 0, 0))
        assert np.allclose(new_focal, [6 * alpha, 0, 0])

    def test_target_equal_to_focal_keeps_focal(self, viewport):
        _, new_focal = step(viewport, 1, target_point=(0, 0, 0))
        assert np.allclose(new_focal, [0, 0, 0])

    def test_view_direction_is_preserved(self, viewport):
        pos = np.array([3.0, 4.0, 12.0])
        focal = np.array([1.0, 1.0, 2.0])
        old_dir = (pos - focal) / np.linalg.norm(pos - focal)

        new_pos, new_focal = step(
            viewport,
            1,
            position=pos,
            focal_point=focal,
            target_point=(5, 5, 5),
        )
        new_dir = (new_pos - new_focal) / np.linalg.norm(new_pos - new_focal)

        assert np.allclose(old_dir, new_dir)

    def test_zoom_in_focal_is_clamped_to_bounds(self, viewport):
        bounds = (-1, 1, -1, 1, -1, 1)
        _, new_focal = step(
            viewport,
            1,
            zoom_factor=0.35,
            target_point=(50, 50, 50),
            bounds=bounds,
        )
        assert np.all(new_focal >= [-1, -1, -1])
        assert np.all(new_focal <= [1, 1, 1])

    def test_distance_is_multiplied_by_one_plus_step(self, viewport):
        new_pos, new_focal = step(viewport, -1, zoom_factor=0.25)
        assert dist(new_pos, new_focal) == pytest.approx(10 * 1.25)

    def test_distance_never_above_max_dist(self, viewport):
        new_pos, new_focal = step(viewport, -1, max_dist=10.5, zoom_factor=0.35)
        assert dist(new_pos, new_focal) == pytest.approx(10.5)

    def test_focal_moves_towards_volume_center(self, viewport):
        focal = np.array([4.0, 0.0, 0.0])
        _, new_focal = step(
            viewport,
            -1,
            position=(4, 0, 10),
            focal_point=focal,
            volume_center=(0, 0, 0),
        )
        assert 0.0 < new_focal[0] < 4.0

    def test_focal_does_not_overshoot_center(self, viewport):
        focal = np.array([4.0, 0.0, 0.0])
        _, new_focal = step(
            viewport,
            -1,
            position=(4, 0, 10),
            focal_point=focal,
            volume_center=(0, 0, 0),
            zoom_factor=0.35,
        )
        assert new_focal[0] >= 0.0

    def test_focal_already_on_center_stays(self, viewport):
        _, new_focal = step(viewport, -1, volume_center=(0, 0, 0))
        assert np.allclose(new_focal, [0, 0, 0])

    def test_volume_center_none_uses_focal_point(self, viewport):
        _, new_focal = step(
            viewport,
            -1,
            focal_point=(2, 0, 0),
            position=(2, 0, 10),
            volume_center=None,
        )
        assert np.allclose(new_focal, [2, 0, 0])

    def test_homing_fraction_is_within_expected_range(self, viewport):
        focal = np.array([10.0, 0.0, 0.0])
        _, new_focal = step(
            viewport,
            -1,
            position=(10, 0, 10),
            focal_point=focal,
            volume_center=(0, 0, 0),
        )
        fraction = (focal[0] - new_focal[0]) / focal[0]
        assert 0.10 <= fraction <= 0.65

    def test_homing_is_stronger_closer_to_global_view(self, viewport):
        focal = np.array([10.0, 0.0, 0.0])

        def fraction(cam_dist):
            _, nf = step(
                viewport,
                -1,
                position=(10, 0, cam_dist),
                focal_point=focal,
                volume_center=(0, 0, 0),
                zoom_factor=0.1,
                min_dist=1.0,
                max_dist=100.0,
            )
            return (focal[0] - nf[0]) / focal[0]

        assert fraction(40.0) > fraction(2.0)

    def test_infinite_max_dist_uses_fallback_branch(self, viewport):
        new_pos, new_focal = step(
            viewport,
            -1,
            position=(4, 0, 10),
            focal_point=(4, 0, 0),
            max_dist=np.inf,
        )
        assert np.all(np.isfinite(new_pos))
        assert dist(new_pos, new_focal) == pytest.approx(10 * 1.2)
        assert 0.0 < new_focal[0] < 4.0

    def test_zoom_out_focal_is_clamped_to_bounds(self, viewport):
        bounds = (-1, 1, -1, 1, -1, 1)
        _, new_focal = step(
            viewport,
            -1,
            position=(0, 0, 10),
            focal_point=(0, 0, 0),
            volume_center=(100, 100, 100),
            zoom_factor=0.35,
            bounds=bounds,
        )
        assert np.all(new_focal >= [-1, -1, -1])
        assert np.all(new_focal <= [1, 1, 1])

    def test_zoom_in_then_out_returns_to_same_distance(self, viewport):
        pos, focal = np.array([0.0, 0, 10]), np.zeros(3)
        p1, f1 = step(viewport, 1, position=pos, focal_point=focal, target_point=focal, zoom_factor=0.2)
        p2, f2 = step(viewport, -1, position=p1, focal_point=f1, volume_center=f1, zoom_factor=0.2)
        assert dist(p2, f2) == pytest.approx(10.0)
