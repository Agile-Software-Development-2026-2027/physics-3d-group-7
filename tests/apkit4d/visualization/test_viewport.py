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
