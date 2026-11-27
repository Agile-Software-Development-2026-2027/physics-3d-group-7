import gc

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
from apkit4d.visualization.viewport import (
    DEFAULT_COLORMAP,
    FAST_SCROLL_THRESHOLD,
    FULL_QUALITY_DELAY,
    MOVING_IMAGE_SAMPLE_DISTANCE,
    RoiMode,
    ScalarBarMode,
    Viewport,
    VisSubRoiMode,
)
from apkit4d.visualization.vis_sub_roi import (
    DEFAULT_BLOB_RGB,
    DEFAULT_OUTSIDE_OPACITY,
    VisSubRoiState,
)


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

    def test_volume_visibility_is_preserved_when_volume_is_added_or_replaced(self, viewport):
        viewport.set_volume_visible(False)
        viewport.show_volume(make_grid(), reset_camera=False)
        assert viewport.plotter.actors["volume"].GetVisibility() == 0

        viewport.show_volume(make_grid(6), reset_camera=False)
        assert viewport.plotter.actors["volume"].GetVisibility() == 0

        viewport.set_volume_visible(True)
        assert viewport.plotter.actors["volume"].GetVisibility() == 1

    def test_outline_visibility_is_preserved_when_volume_is_added_or_replaced(self, viewport):
        viewport.set_outline_visible(False)
        viewport.show_volume(make_grid(), reset_camera=False)
        assert viewport.plotter.actors["outline"].GetVisibility() == 0

        viewport.show_volume(make_grid(6), reset_camera=False)
        assert viewport.plotter.actors["outline"].GetVisibility() == 0

        viewport.set_outline_visible(True)
        assert viewport.plotter.actors["outline"].GetVisibility() == 1

    def test_scalar_bar_visibility_is_preserved_when_volume_is_added_or_replaced(self, viewport):
        viewport.set_scalar_bar_visible(False)
        viewport.show_volume(make_grid(), reset_camera=False)
        assert viewport.plotter.scalar_bars["values"].GetVisibility() == 0

        viewport.show_volume(make_grid(6), reset_camera=False)
        assert viewport.plotter.scalar_bars["values"].GetVisibility() == 0

        viewport.set_scalar_bar_visible(True)
        assert viewport.plotter.scalar_bars["values"].GetVisibility() == 1

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


class TestWheelRendering:
    def test_no_automatic_redraw(self, viewport):
        assert not viewport.plotter.render_timer.isActive()

    def test_volume_resolution_is_lowered_while_moving(self, viewport):
        viewport.show_volume(make_grid())
        mapper = viewport.plotter.actors["volume"].mapper
        window = viewport.plotter.render_window
        iren = viewport.plotter.iren.interactor
        # StartEvent is what VTK sends before every redraw
        window.SetDesiredUpdateRate(iren.GetDesiredUpdateRate())
        window.InvokeEvent("StartEvent")
        assert mapper.GetImageSampleDistance() == MOVING_IMAGE_SAMPLE_DISTANCE
        window.SetDesiredUpdateRate(iren.GetStillUpdateRate())
        window.InvokeEvent("StartEvent")
        assert mapper.GetImageSampleDistance() == 1.0

    def test_volume_sampling_follows_the_voxel_spacing(self, viewport):
        viewport.show_volume(make_grid())
        assert viewport.plotter.actors["volume"].mapper.GetLockSampleDistanceToInputSpacing() == 1

    def test_volume_quality_without_volume_does_nothing(self, viewport):
        viewport.plotter.render_window.InvokeEvent("StartEvent")
        viewport.plotter.close()
        viewport._set_volume_quality(None, "StartEvent")

    def test_wheel_step_uses_moving_quality(self, viewport):
        viewport.show_volume(make_grid())
        viewport._apply_wheel_zoom(direction=1)
        iren = viewport.plotter.iren.interactor
        assert viewport.plotter.render_window.GetDesiredUpdateRate() == iren.GetDesiredUpdateRate()
        assert viewport._full_quality_timer.isActive()

    def test_full_quality_when_the_wheel_stops(self, viewport):
        viewport.show_volume(make_grid())
        viewport._apply_wheel_zoom(direction=1)
        assert viewport._full_quality_timer.isSingleShot()
        # this is what the timer calls when it fires, called directly so the test does not wait
        viewport._request_full_quality_render()
        iren = viewport.plotter.iren.interactor
        assert viewport.plotter.render_window.GetDesiredUpdateRate() == iren.GetStillUpdateRate()

    def test_full_quality_waits_longer_than_a_fast_scroll_step(self, viewport):
        assert FULL_QUALITY_DELAY > FAST_SCROLL_THRESHOLD
        assert viewport._full_quality_timer.interval() == round(FULL_QUALITY_DELAY * 1000)

    def test_no_full_quality_redraw_during_a_drag(self, viewport):
        viewport.show_volume(make_grid())
        iren = viewport.plotter.iren.interactor
        style = iren.GetInteractorStyle()
        style.StartRotate()
        viewport._request_full_quality_render()
        assert viewport.plotter.render_window.GetDesiredUpdateRate() == iren.GetDesiredUpdateRate()
        style.EndRotate()

    def test_full_quality_after_close_does_nothing(self, viewport):
        viewport.plotter.close()
        viewport._request_full_quality_render()

    def test_moving_quality_after_close_does_nothing(self, viewport):
        viewport.plotter.close()
        viewport._request_moving_render()
        assert not viewport._full_quality_timer.isActive()

    def test_clear_goes_back_to_full_quality(self, viewport):
        viewport.show_volume(make_grid())
        viewport._apply_wheel_zoom(direction=1)
        viewport.clear()
        iren = viewport.plotter.iren.interactor
        assert not viewport._full_quality_timer.isActive()
        assert viewport.plotter.render_window.GetDesiredUpdateRate() == iren.GetStillUpdateRate()

    def test_scene_changes_ask_for_a_redraw_instead_of_drawing(self, viewport, monkeypatch):
        draws, requests = [], []
        monkeypatch.setattr(viewport.plotter, "render", lambda: draws.append(1))
        monkeypatch.setattr(viewport, "_request_render", lambda: requests.append(1))
        viewport.show_volume(make_grid())
        viewport.show_blobs(make_poly())
        viewport.clear()
        assert draws == []
        assert len(requests) == 3

    def test_wheel_event_does_not_reach_the_default_zoom(self, viewport):
        viewport.show_volume(make_grid())
        iren = viewport.plotter.iren.interactor
        calls = []
        # the default VTK zoom listens with priority 0, below our observers
        iren.AddObserver("MouseWheelForwardEvent", lambda *_: calls.append("forward"), 0.0)
        iren.AddObserver("MouseWheelBackwardEvent", lambda *_: calls.append("backward"), 0.0)
        before = viewport.plotter.camera.position
        iren.MouseWheelForwardEvent()
        assert viewport.plotter.camera.position != before
        iren.MouseWheelBackwardEvent()
        assert calls == []

    def test_wheel_zoom_stays_inside_the_limits(self, viewport, monkeypatch):
        # every step counts as a fast scroll, so the steps grow to the biggest one
        monkeypatch.setattr("apkit4d.visualization.viewport.FAST_SCROLL_THRESHOLD", float("inf"))
        viewport.show_volume(make_grid())
        iren = viewport.plotter.iren.interactor
        camera = viewport.plotter.camera
        for _ in range(100):
            iren.MouseWheelForwardEvent()
        assert dist(camera.position, camera.focal_point) == pytest.approx(viewport.min_zoom_dist)
        for _ in range(100):
            iren.MouseWheelBackwardEvent()
        assert dist(camera.position, camera.focal_point) == pytest.approx(viewport.max_zoom_dist)

    @pytest.mark.parametrize("event", ["InteractionEvent", "EndInteractionEvent"])
    def test_drag_zoom_stays_inside_the_limits(self, viewport, event):
        viewport.show_volume(make_grid())
        camera = viewport.plotter.camera
        # the camera gets closer than the limit, as a zoom with the right mouse button can do
        focal = np.array(camera.focal_point)
        direction = (np.array(camera.position) - focal) / dist(camera.position, focal)
        camera.position = tuple(focal + direction * viewport.min_zoom_dist / 2)
        viewport.plotter.iren.interactor.InvokeEvent(event)
        assert dist(camera.position, camera.focal_point) == pytest.approx(viewport.min_zoom_dist)


class TestViewportRayPicking:
    def test_intersect_ray_bounds_hits_front_face(self, viewport):
        bounds = (0.0, 10.0, 0.0, 10.0, 0.0, 10.0)
        # ray that starts at z=20 and points straight to the center of the box (5, 5, -5)
        ray_start = np.array([5.0, 5.0, 20.0])
        ray_end = np.array([5.0, 5.0, -5.0])

        hit = viewport._ray_intersects_bounds(ray_start, ray_end, bounds)
        assert hit is not None
        # need to hit the front face of the box at z=10.0, in the point (5, 5, 10)
        np.testing.assert_allclose(hit, [5.0, 5.0, 10.0])

    def test_intersect_ray_bounds_returns_none_when_missing_box(self, viewport):
        bounds = (0.0, 10.0, 0.0, 10.0, 0.0, 10.0)
        # ray that go outside the box, starting at (50, 50, 20) and pointing to (50, 50, -5)
        ray_start = np.array([50.0, 50.0, 20.0])
        ray_end = np.array([50.0, 50.0, -5.0])

        hit = viewport._ray_intersects_bounds(ray_start, ray_end, bounds)
        assert hit is None

    def test_pick_volume_bounds_point_returns_none_without_volume(self, viewport):
        assert viewport.pick_volume_bounds_point((100, 100)) is None

    def test_pick_volume_bounds_point_hits_center_and_handles_outside(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=True)
        # place the camera in front of the volume, looking at its center
        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

        # get coordinates of the center of the volume in world space
        renderer = viewport.plotter.renderer
        renderer.SetWorldPoint(2.0, 2.0, 2.0, 1.0)
        renderer.WorldToDisplay()
        cx, cy, _ = renderer.GetDisplayPoint()

        hit = viewport.pick_volume_bounds_point((int(round(cx)), int(round(cy))))
        assert hit is not None
        # the center of make_grid() (5x5x5 with spacing 1) is at (2.0, 2.0, 2.0)
        np.testing.assert_allclose(hit, [2.0, 2.0, 4.0], atol=0.2)


class TestViewportRoiDragSelection:
    def test_start_roi_selection_ignored_without_volume(self, viewport):
        viewport.start_roi_selection()
        assert viewport.roi_mode == RoiMode.INACTIVE

    def test_full_click_drag_release_creates_3d_roi_preview(self, viewport):
        viewport.resize(600, 600)
        viewport.plotter.render_window.SetSize(600, 600)
        viewport.show_volume(make_grid(), reset_camera=True)

        # place the camera in front of the volume on the z-axis,
        # above the center of the volume (2, 2, 2)
        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

        viewport.start_roi_selection()
        assert viewport.roi_mode == RoiMode.WAITING_FIRST_POINT

        renderer = viewport.plotter.renderer

        def world_to_px(wx, wy, wz):
            renderer.SetWorldPoint(wx, wy, wz, 1.0)
            renderer.WorldToDisplay()
            dx, dy, _ = renderer.GetDisplayPoint()
            return int(round(dx)), int(round(dy))

        iren = viewport.plotter.iren.interactor

        # Click on point (1.0, 1.0, 4.0)
        px1, py1 = world_to_px(1.0, 1.0, 4.0)
        iren.SetEventPosition(px1, py1)
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        assert viewport.roi_mode == RoiMode.DRAGGING

        # drag to point (3.0, 3.0, 4.0)
        px2, py2 = world_to_px(3.0, 3.0, 4.0)
        iren.SetEventPosition(px2, py2)
        viewport._on_mouse_move(None, "MouseMoveEvent")

        assert "roi_preview" in viewport.plotter.actors
        assert viewport.current_roi is not None
        np.testing.assert_allclose(
            viewport.current_roi.bounds,
            (1.0, 3.0, 1.0, 3.0, 0.0, 4.0),
            atol=0.25,
        )

        # mouse release should finalize the ROI selection
        viewport._on_left_button_release(None, "LeftButtonReleaseEvent")
        assert viewport.roi_mode == RoiMode.EDITING

        # canceling the ROI selection should remove the preview and reset the mode
        viewport.cancel_roi_selection()
        assert viewport.roi_mode == RoiMode.INACTIVE
        assert viewport.current_roi is None
        assert "roi_preview" not in viewport.plotter.actors

    def test_box_widget_enabled_in_editing_and_clamps_handle_drag(self, viewport):
        viewport.resize(600, 600)
        viewport.plotter.render_window.SetSize(600, 600)
        viewport.show_volume(make_grid(), reset_camera=True)

        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

        viewport.start_roi_selection()

        renderer = viewport.plotter.renderer

        def world_to_px(wx, wy, wz):
            renderer.SetWorldPoint(wx, wy, wz, 1.0)
            renderer.WorldToDisplay()
            dx, dy, _ = renderer.GetDisplayPoint()
            return int(round(dx)), int(round(dy))

        iren = viewport.plotter.iren.interactor

        # Click and drag to create initial ROI
        iren.SetEventPosition(*world_to_px(1.0, 1.0, 4.0))
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        iren.SetEventPosition(*world_to_px(3.0, 3.0, 4.0))
        viewport._on_mouse_move(None, "MouseMoveEvent")
        viewport._on_left_button_release(None, "LeftButtonReleaseEvent")

        # Verify vtkBoxWidget2 is enabled and rotation is locked
        assert viewport.roi_mode == RoiMode.EDITING
        assert viewport._roi_box_widget is not None
        assert viewport._roi_box_widget.GetEnabled() == 1
        assert viewport._roi_box_widget.GetRotationEnabled() == 0

        # Simulate user dragging the Z handles to [1.0, 2.5] and X handle outside volume (-5.0)
        viewport._roi_box_rep.PlaceWidget([-5.0, 3.5, 1.0, 3.0, 1.0, 2.5])
        viewport._on_box_widget_interaction(None, "InteractionEvent")
        viewport._on_box_widget_end_interaction(None, "EndInteractionEvent")

        # X min must be clamped to 0.0, Z must be updated to [1.0, 2.5]
        assert viewport.current_roi is not None
        np.testing.assert_allclose(
            viewport.current_roi.bounds,
            (0.0, 3.5, 1.0, 3.0, 1.0, 2.5),
        )

        # Cancel must turn off the widget
        viewport.cancel_roi_selection()
        assert viewport._roi_box_widget.GetEnabled() == 0

    def test_accept_roi_selection_emits_signal_and_cleans_up_preview(self, viewport):
        viewport.resize(600, 600)
        viewport.plotter.render_window.SetSize(600, 600)
        viewport.show_volume(make_grid(), reset_camera=True)

        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

        started_calls = []
        updated_rois = []
        accepted_rois = []

        viewport.roi_selection_started.connect(lambda: started_calls.append(True))
        viewport.roi_updated.connect(lambda r: updated_rois.append(r))
        viewport.roi_accepted.connect(lambda r: accepted_rois.append(r))

        # Calling accept when not in EDITING mode should return None and emit nothing
        assert viewport.accept_roi_selection() is None
        assert len(accepted_rois) == 0

        # Starting selection then accepting before drawing anything must leave mode INACTIVE
        viewport.start_roi_selection()
        assert viewport.roi_mode == RoiMode.WAITING_FIRST_POINT
        assert viewport.accept_roi_selection() is None
        assert viewport.roi_mode == RoiMode.INACTIVE
        assert len(accepted_rois) == 0
        started_calls.clear()

        viewport.start_roi_selection()
        assert len(started_calls) == 1

        renderer = viewport.plotter.renderer

        def world_to_px(wx, wy, wz):
            renderer.SetWorldPoint(wx, wy, wz, 1.0)
            renderer.WorldToDisplay()
            dx, dy, _ = renderer.GetDisplayPoint()
            return int(round(dx)), int(round(dy))

        iren = viewport.plotter.iren.interactor
        iren.SetEventPosition(*world_to_px(1.0, 1.0, 4.0))
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        iren.SetEventPosition(*world_to_px(3.0, 3.0, 4.0))
        viewport._on_mouse_move(None, "MouseMoveEvent")
        viewport._on_left_button_release(None, "LeftButtonReleaseEvent")

        assert len(updated_rois) >= 1

        # Adjust bounds via the box widget representation before accepting
        viewport._roi_box_rep.PlaceWidget([0.5, 3.5, 1.0, 3.0, 0.5, 2.5])
        viewport._on_box_widget_interaction(None, "InteractionEvent")

        # Accept the ROI
        final_roi = viewport.accept_roi_selection()
        assert final_roi is not None
        assert len(accepted_rois) == 1
        assert accepted_rois[0] == final_roi
        np.testing.assert_allclose(final_roi.bounds, (0.5, 3.5, 1.0, 3.0, 0.5, 2.5))

        # Verify state is back to INACTIVE and preview/widget are turned off
        assert viewport.roi_mode == RoiMode.INACTIVE
        assert viewport._roi_box_widget.GetEnabled() == 0
        assert "roi_preview" not in viewport.plotter.actors

    def test_set_roi_preview_and_cancel_signal(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=True)

        cancelled_calls = []
        viewport.roi_cancelled.connect(lambda: cancelled_calls.append(True))

        custom_roi = RegionOfInterest(x_min=1.0, x_max=3.0, y_min=1.0, y_max=3.0, z_min=0.5, z_max=2.5)
        viewport.set_roi_preview(custom_roi)

        assert viewport.roi_mode == RoiMode.EDITING
        assert viewport.current_roi == custom_roi
        assert viewport._roi_box_widget is not None
        assert viewport._roi_box_widget.GetEnabled() == 1
        assert "roi_preview" in viewport.plotter.actors

        viewport.cancel_roi_selection()
        assert len(cancelled_calls) == 1
        assert viewport.roi_mode == RoiMode.INACTIVE

    def test_click_outside_volume_stays_waiting_for_first_point(self, viewport):
        viewport.resize(600, 600)
        viewport.plotter.render_window.SetSize(600, 600)
        viewport.show_volume(make_grid(), reset_camera=True)

        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

        viewport.start_roi_selection()
        assert viewport.roi_mode == RoiMode.WAITING_FIRST_POINT

        # Click at pixel (1, 1) in the corner far outside the volume
        iren = viewport.plotter.iren.interactor
        iren.SetEventPosition(1, 1)
        viewport._on_left_button_press(None, "LeftButtonPressEvent")

        assert viewport.roi_mode == RoiMode.WAITING_FIRST_POINT
        assert viewport.current_roi is None

    def test_quick_click_without_mouse_move_creates_valid_roi_on_release(self, viewport):
        viewport.resize(600, 600)
        viewport.plotter.render_window.SetSize(600, 600)
        viewport.show_volume(make_grid(), reset_camera=True)

        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

        viewport.start_roi_selection()

        renderer = viewport.plotter.renderer
        renderer.SetWorldPoint(2.0, 2.0, 4.0, 1.0)
        renderer.WorldToDisplay()
        dx, dy, _ = renderer.GetDisplayPoint()

        iren = viewport.plotter.iren.interactor
        iren.SetEventPosition(int(round(dx)), int(round(dy)))

        # Press and immediately release without calling _on_mouse_move
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        assert viewport.roi_mode == RoiMode.DRAGGING
        assert viewport.current_roi is None

        viewport._on_left_button_release(None, "LeftButtonReleaseEvent")
        assert viewport.roi_mode == RoiMode.EDITING
        assert viewport.current_roi is not None
        assert "roi_preview" in viewport.plotter.actors
        assert viewport._roi_box_widget is not None
        assert viewport._roi_box_widget.GetEnabled() == 1

    def test_set_roi_preview_ignored_without_volume(self, viewport):
        custom_roi = RegionOfInterest(x_min=1.0, x_max=3.0, y_min=1.0, y_max=3.0, z_min=0.5, z_max=2.5)
        viewport.set_roi_preview(custom_roi)
        assert viewport.roi_mode == RoiMode.INACTIVE
        assert viewport.current_roi is None

    def test_clear_resets_roi_editing_state_and_disables_widget(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=True)
        custom_roi = RegionOfInterest(x_min=1.0, x_max=3.0, y_min=1.0, y_max=3.0, z_min=0.5, z_max=2.5)
        viewport.set_roi_preview(custom_roi)
        assert viewport.roi_mode == RoiMode.EDITING
        assert viewport._roi_box_widget.GetEnabled() == 1

        viewport.clear()
        assert viewport.roi_mode == RoiMode.INACTIVE
        assert viewport.current_roi is None
        assert viewport._roi_box_widget.GetEnabled() == 0

    @staticmethod
    def _drag_box(viewport, dx=0.0, dy=0.0):
        """Simulates one mouse move that translates the whole box by (dx, dy), like VTK does:
        the delta is added to the bounds the widget holds right now."""
        b = viewport._roi_box_rep.GetBounds()
        viewport._roi_box_rep.PlaceWidget([b[0] + dx, b[1] + dx, b[2] + dy, b[3] + dy, b[4], b[5]])
        viewport._on_box_widget_interaction(None, "InteractionEvent")

    @staticmethod
    def _box_with_x_between_1_and_3(viewport):
        viewport.show_volume(make_grid(), reset_camera=True)  # volume bounds are 0..4 on every axis
        viewport.set_roi_preview(
            RegionOfInterest(x_min=1.0, x_max=3.0, y_min=1.0, y_max=3.0, z_min=1.0, z_max=3.0)
        )
        viewport._on_box_widget_start_interaction(None, "StartInteractionEvent")

    def test_pushing_box_against_edge_stops_it_without_shrinking(self, viewport):
        self._box_with_x_between_1_and_3(viewport)

        for _ in range(5):  # the cursor keeps going far beyond the edge
            self._drag_box(viewport, dx=1.0)

        x_min, x_max, *_ = viewport.current_roi.bounds
        assert (x_min, x_max) == pytest.approx((2.0, 4.0))  # same width 2, stopped at the edge
        np.testing.assert_allclose(viewport._roi_box_rep.GetBounds()[0:2], (2.0, 4.0))

    def test_box_does_not_move_back_until_cursor_is_inside_again(self, viewport):
        self._box_with_x_between_1_and_3(viewport)

        for _ in range(3):  # the virtual box goes to x = (4, 6), the shown one stops at (2, 4)
            self._drag_box(viewport, dx=1.0)
        assert viewport.current_roi.bounds[0:2] == pytest.approx((2.0, 4.0))

        self._drag_box(viewport, dx=-1.0)  # virtual (3, 5): still beyond the edge
        assert viewport.current_roi.bounds[0:2] == pytest.approx((2.0, 4.0))

        self._drag_box(viewport, dx=-1.0)  # virtual (2, 4): the cursor is exactly at the edge
        assert viewport.current_roi.bounds[0:2] == pytest.approx((2.0, 4.0))

        self._drag_box(viewport, dx=-1.0)  # virtual (1, 3): the box follows again
        assert viewport.current_roi.bounds[0:2] == pytest.approx((1.0, 3.0))

    def test_box_slides_along_edge_when_cursor_moves_on_the_other_axis(self, viewport):
        self._box_with_x_between_1_and_3(viewport)

        self._drag_box(viewport, dx=3.0)  # pushed against the x edge, virtual x = (4, 6)
        self._drag_box(viewport, dy=0.5)  # moving up while still outside on x

        x_min, x_max, y_min, y_max, *_ = viewport.current_roi.bounds
        assert (x_min, x_max) == pytest.approx((2.0, 4.0))  # still stopped on x
        assert (y_min, y_max) == pytest.approx((1.5, 3.5))  # but it follows on y

    def test_new_drag_starts_from_the_displayed_box(self, viewport):
        self._box_with_x_between_1_and_3(viewport)

        for _ in range(3):  # virtual (4, 6), shown (2, 4)
            self._drag_box(viewport, dx=1.0)
        viewport._on_box_widget_end_interaction(None, "EndInteractionEvent")

        # new drag: the virtual box is forgotten, so it moves back immediately
        viewport._on_box_widget_start_interaction(None, "StartInteractionEvent")
        self._drag_box(viewport, dx=-1.0)
        assert viewport.current_roi.bounds[0:2] == pytest.approx((1.0, 3.0))

    def test_resizing_a_face_past_edge_stops_at_edge_and_waits_for_cursor(self, viewport):
        self._box_with_x_between_1_and_3(viewport)

        def drag_max_x_face(dx):
            b = viewport._roi_box_rep.GetBounds()
            viewport._roi_box_rep.PlaceWidget([b[0], b[1] + dx, b[2], b[3], b[4], b[5]])
            viewport._on_box_widget_interaction(None, "InteractionEvent")

        drag_max_x_face(+3.0)  # virtual max x = 6, the face stops at 4
        assert viewport.current_roi.bounds[0:2] == pytest.approx((1.0, 4.0))

        drag_max_x_face(-1.0)  # virtual max x = 5: the cursor is still outside
        assert viewport.current_roi.bounds[0:2] == pytest.approx((1.0, 4.0))

        drag_max_x_face(-2.0)  # virtual max x = 3: the face follows again
        assert viewport.current_roi.bounds[0:2] == pytest.approx((1.0, 3.0))


VOLUME = (0.0, 4.0, 0.0, 4.0, 0.0, 4.0)


class TestBoxMovementHelpers:
    def test_pure_translation_is_detected(self):
        old = (1.0, 3.0, 1.0, 3.0, 1.0, 3.0)
        new = (2.0, 4.0, 1.5, 3.5, 1.0, 3.0)  # moved on x and y, same sizes

        assert Viewport._is_pure_translation(new, old, tol=1e-6)

    def test_resize_of_one_face_is_not_a_translation(self):
        old = (1.0, 3.0, 1.0, 3.0, 1.0, 3.0)
        new = (1.0, 3.5, 1.0, 3.0, 1.0, 3.0)  # only x max moved

        assert not Viewport._is_pure_translation(new, old, tol=1e-6)

    def test_size_difference_below_tolerance_counts_as_translation(self):
        old = (1.0, 3.0, 1.0, 3.0, 1.0, 3.0)
        new = (2.0, 4.0 + 1e-9, 1.0, 3.0, 1.0, 3.0)  # float noise

        assert Viewport._is_pure_translation(new, old, tol=1e-6)

    def test_slide_leaves_box_inside_volume_unchanged(self):
        virtual = (1.5, 3.5, 1.0, 3.0, 1.0, 3.0)

        result = Viewport._slide_inside_volume(virtual, (2.0, 2.0, 2.0), VOLUME)

        np.testing.assert_allclose(result, virtual)

    def test_slide_past_max_edge_stops_at_edge_keeping_size(self):
        virtual = (3.0, 5.0, 1.0, 3.0, 1.0, 3.0)  # x sticks out by 1

        result = Viewport._slide_inside_volume(virtual, (2.0, 2.0, 2.0), VOLUME)

        np.testing.assert_allclose(result, (2.0, 4.0, 1.0, 3.0, 1.0, 3.0))

    def test_slide_past_min_edge_stops_at_edge_keeping_size(self):
        virtual = (-1.0, 1.0, 1.0, 3.0, 1.0, 3.0)

        result = Viewport._slide_inside_volume(virtual, (2.0, 2.0, 2.0), VOLUME)

        np.testing.assert_allclose(result, (0.0, 2.0, 1.0, 3.0, 1.0, 3.0))

    def test_slide_is_independent_on_each_axis(self):
        # far outside on x, inside on y: x stops at the edge, y follows
        virtual = (50.0, 52.0, 1.5, 3.5, 1.0, 3.0)

        result = Viewport._slide_inside_volume(virtual, (2.0, 2.0, 2.0), VOLUME)

        np.testing.assert_allclose(result, (2.0, 4.0, 1.5, 3.5, 1.0, 3.0))

    def test_slide_box_as_big_as_volume_cannot_move(self):
        virtual = (1.0, 5.0, 0.0, 4.0, 0.0, 4.0)

        result = Viewport._slide_inside_volume(virtual, (4.0, 4.0, 4.0), VOLUME)

        np.testing.assert_allclose(result, VOLUME)


def lut_colors(viewport) -> np.ndarray:
    lut = viewport.plotter.actors["volume"].mapper.lookup_table
    return np.array(lut.values)[:, :3]


def colormap_colors(name: str) -> np.ndarray:
    return np.array(pv.LookupTable(cmap=name).values)[:, :3]


def text_colors(viewport) -> list[tuple[float, float, float]]:
    scalar_bar = viewport.plotter.scalar_bars["values"]
    axes = viewport.plotter.renderer.axes_actor
    return [
        scalar_bar.GetLabelTextProperty().GetColor(),
        scalar_bar.GetTitleTextProperty().GetColor(),
        axes.GetXAxisCaptionActor2D().GetCaptionTextProperty().GetColor(),
        axes.GetYAxisCaptionActor2D().GetCaptionTextProperty().GetColor(),
        axes.GetZAxisCaptionActor2D().GetCaptionTextProperty().GetColor(),
    ]


class TestAppearance:
    def test_volume_starts_with_the_default_colormap(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        assert np.allclose(lut_colors(viewport), colormap_colors(DEFAULT_COLORMAP))

    def test_set_colormap_changes_the_colors_and_keeps_the_opacity(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        lut = viewport.plotter.actors["volume"].mapper.lookup_table
        alpha = np.array(lut.values)[:, 3]

        viewport.set_colormap("viridis")

        assert np.allclose(lut_colors(viewport), colormap_colors("viridis"))
        assert np.array_equal(np.array(lut.values)[:, 3], alpha)
        assert viewport.plotter.scalar_bars["values"].GetLookupTable() is lut

    def test_colormap_chosen_before_the_volume_is_used_by_it(self, viewport):
        viewport.set_colormap("viridis")
        viewport.show_volume(make_grid(), reset_camera=False)
        assert np.allclose(lut_colors(viewport), colormap_colors("viridis"))

    def test_colormap_stays_on_the_next_frames(self, viewport):
        viewport.show_volume(make_grid(5), reset_camera=False)
        viewport.set_colormap("viridis")

        viewport.show_volume(make_grid(5), reset_camera=False)
        assert np.allclose(lut_colors(viewport), colormap_colors("viridis"))

        viewport.show_volume(make_grid(8), reset_camera=False)
        assert np.allclose(lut_colors(viewport), colormap_colors("viridis"))

    def test_set_colormap_rejects_an_unknown_name(self, viewport):
        with pytest.raises(ValueError):
            viewport.set_colormap("not_a_colormap")

    def test_set_volume_opacity_scales_the_opacity_unit_distance(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        prop = viewport.plotter.actors["volume"].prop
        base = prop.opacity_unit_distance

        viewport.set_volume_opacity(4.0)
        assert prop.opacity_unit_distance == pytest.approx(base / 4)

        viewport.set_volume_opacity(0.5)
        assert prop.opacity_unit_distance == pytest.approx(base * 2)

    def test_volume_opacity_stays_on_a_volume_of_another_size(self, viewport):
        viewport.show_volume(make_grid(5), reset_camera=False)
        viewport.set_volume_opacity(2.0)

        viewport.show_volume(make_grid(9), reset_camera=False)

        grid = make_grid(9)
        base = grid.length / (np.mean(grid.dimensions) - 1)
        prop = viewport.plotter.actors["volume"].prop
        assert prop.opacity_unit_distance == pytest.approx(base / 2)

    @pytest.mark.parametrize("opacity", [0.0, -1.0])
    def test_set_volume_opacity_rejects_values_not_above_zero(self, viewport, opacity):
        with pytest.raises(ValueError):
            viewport.set_volume_opacity(opacity)

    def test_set_background_changes_the_background(self, viewport):
        viewport.set_background("#2b2d31")
        assert viewport.plotter.renderer.background_color.hex_rgb == "#2b2d31"

    def test_outline_color_is_used_and_kept(self, viewport):
        viewport.set_outline_color("#1f2328")
        viewport.show_volume(make_grid(5), reset_camera=False)
        assert viewport.plotter.actors["outline"].prop.color.hex_rgb == "#1f2328"

        viewport.set_outline_color("red")
        assert viewport.plotter.actors["outline"].prop.color.hex_rgb == "#ff0000"

        viewport.show_volume(make_grid(8), reset_camera=False)
        assert viewport.plotter.actors["outline"].prop.color.hex_rgb == "#ff0000"

    def test_text_color_paints_the_scalar_bar_and_the_axes(self, viewport):
        viewport.show_volume(make_grid(5), reset_camera=False)
        viewport.set_text_color("white")
        assert all(color == pytest.approx((1.0, 1.0, 1.0)) for color in text_colors(viewport))

        viewport.show_volume(make_grid(8), reset_camera=False)
        assert all(color == pytest.approx((1.0, 1.0, 1.0)) for color in text_colors(viewport))

    @pytest.mark.parametrize(
        ("method", "value"),
        [
            ("set_colormap", "viridis"),
            ("set_volume_opacity", 2.0),
            ("set_background", "black"),
            ("set_outline_color", "red"),
            ("set_text_color", "white"),
        ],
    )
    def test_changes_ask_for_a_redraw(self, viewport, monkeypatch, method, value):
        viewport.show_volume(make_grid(), reset_camera=False)
        calls = []
        monkeypatch.setattr(viewport, "_request_render", lambda: calls.append(True))

        getattr(viewport, method)(value)

        assert calls

    def test_show_volume_updates_in_place_when_grid_matches_and_force_update_is_false(self, viewport):
        first = make_grid(5)
        first.point_data["values"] = np.full(first.n_points, 1.0)
        viewport.show_volume(first, reset_camera=False)
        cached_grid = viewport._volume_grid

        second = make_grid(5)
        second.point_data["values"] = np.full(second.n_points, 2.0)
        viewport.show_volume(second, reset_camera=False, force_update=False)

        assert viewport._volume_grid is cached_grid
        np.testing.assert_allclose(viewport._volume_grid.point_data["values"], 2.0)
        assert viewport.plotter.actors["volume"].mapper.scalar_range == pytest.approx((2.0, 2.0))

    def test_show_volume_rebuilds_grid_and_transfer_functions_when_force_update_is_true(self, viewport):
        first = make_grid(5)
        first.point_data["values"] = np.linspace(0.0, 1.0, first.n_points)
        viewport.show_volume(first, reset_camera=False)
        cached_grid = viewport._volume_grid

        second = make_grid(5)
        second.point_data["values"] = np.linspace(0.0, 4095.0, second.n_points)
        viewport.show_volume(second, reset_camera=False, force_update=True)

        assert viewport._volume_grid is not cached_grid
        assert viewport.plotter.actors["volume"].mapper.scalar_range == pytest.approx((0.0, 4095.0))
        assert viewport.plotter.actors["volume"].mapper.lookup_table.scalar_range == pytest.approx(
            (0.0, 4095.0)
        )

    def test_show_and_clear_trajectories_and_blob_visibility(self, viewport):
        pts1 = np.array([[0.0, 0.0, 0.0], [5.0, 5.0, 5.0]], dtype=np.float32)
        lines1 = np.array([2, 0, 1], dtype=np.int64)
        poly1 = pv.PolyData(pts1, lines=lines1)
        poly1.point_data["rgb"] = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)

        viewport.show_trajectories(poly1, line_width=3.0)
        assert "tracks_highlighted" in viewport.plotter.actors

        # Updating trajectories reuses the actor cleanly
        pts2 = np.array([[0.0, 0.0, 0.0], [5.0, 5.0, 5.0], [10.0, 5.0, 5.0]], dtype=np.float32)
        lines2 = np.array([3, 0, 1, 2], dtype=np.int64)
        poly2 = pv.PolyData(pts2, lines=lines2)
        poly2.point_data["rgb"] = np.array([[255, 0, 0], [0, 255, 0], [0, 0, 255]], dtype=np.uint8)
        viewport.show_trajectories(poly2, line_width=4.0)
        assert viewport.plotter.actors["tracks_highlighted"].GetProperty().GetLineWidth() == pytest.approx(
            4.0
        )

        # Hiding blobs preserves visibility state across subsequent show_blobs calls
        viewport.show_blobs(make_poly())
        assert viewport.plotter.actors["blobs"].GetVisibility() == 1
        viewport.set_blobs_visible(False)
        assert viewport.plotter.actors["blobs"].GetVisibility() == 0
        viewport.show_blobs(make_poly(2))
        assert viewport.plotter.actors["blobs"].GetVisibility() == 0

        viewport.clear_trajectories()
        assert "tracks_highlighted" not in viewport.plotter.actors

        viewport.show_trajectories(poly1)
        viewport.clear()
        assert "tracks_highlighted" not in viewport.plotter.actors


class TestViewportFpsTicker:
    def test_render_fps_starts_at_zero(self, viewport):
        assert viewport.render_fps == 0.0

    def test_render_end_event_updates_render_fps(self, viewport, monkeypatch):
        now = 10.0
        monkeypatch.setattr("time.perf_counter", lambda: now)

        window = viewport.plotter.render_window
        window.InvokeEvent("EndEvent")
        assert viewport.render_fps == 0.0

        # 3 more EndEvent frames at 50 ms intervals -> 20 FPS
        for _ in range(3):
            now += 0.05
            window.InvokeEvent("EndEvent")

        assert viewport.render_fps == pytest.approx(20.0)


class TestViewportVolumeSubRoi:
    def test_initial_state_defaults_to_disabled_and_one_percent_opacity(self, viewport):
        state = viewport.vis_sub_roi_state
        assert state.enabled is False
        assert state.bounds is None
        assert state.outside_opacity == pytest.approx(DEFAULT_OUTSIDE_OPACITY)

    def test_show_volume_registers_fragment_shader_replacement(self, viewport):
        viewport.show_volume(make_grid(6), reset_camera=False)
        shader_prop = viewport.plotter.actors["volume"].GetShaderProperty()
        assert shader_prop is not None
        assert shader_prop.GetNumberOfShaderReplacements() >= 1

    def test_disable_preserves_bounds_and_outside_opacity(self, viewport):
        grid = pv.ImageData(dimensions=(10, 10, 10), spacing=(1.0, 1.0, 1.0), origin=(5.0, 2.0, 1.0))
        grid.point_data["values"] = np.ones(grid.n_points, dtype=np.float32)
        viewport.show_volume(grid, reset_camera=False)

        viewport.set_vis_sub_roi_outside_opacity(0.05)
        viewport.set_vis_sub_roi_bounds((6.0, 12.0, 3.0, 9.0, 2.0, 8.0))
        viewport.set_vis_sub_roi_enabled(True)
        assert viewport.vis_sub_roi_state.enabled is True

        viewport.set_vis_sub_roi_enabled(False)
        assert viewport.vis_sub_roi_state.enabled is False
        assert viewport.vis_sub_roi_state.bounds == pytest.approx((6.0, 12.0, 3.0, 9.0, 2.0, 8.0))
        assert viewport.vis_sub_roi_state.outside_opacity == pytest.approx(0.05)

    def test_clear_vis_sub_roi_clears_bounds_but_preserves_outside_opacity(self, viewport):
        viewport.show_volume(make_grid(6), reset_camera=False)
        viewport.set_vis_sub_roi_outside_opacity(0.15)
        viewport.set_vis_sub_roi_bounds((1.0, 3.0, 1.0, 3.0, 1.0, 3.0))
        viewport.set_vis_sub_roi_enabled(True)

        viewport.clear_vis_sub_roi()
        assert viewport.vis_sub_roi_state.enabled is False
        assert viewport.vis_sub_roi_state.bounds is None
        assert viewport.vis_sub_roi_state.outside_opacity == pytest.approx(0.15)

    def test_viewport_clear_resets_vis_sub_roi_including_opacity(self, viewport):
        viewport.show_volume(make_grid(6), reset_camera=False)
        viewport.set_vis_sub_roi_outside_opacity(0.25)
        viewport.set_vis_sub_roi_bounds((1.0, 3.0, 1.0, 3.0, 1.0, 3.0))
        viewport.set_vis_sub_roi_enabled(True)

        viewport.clear()
        assert viewport.vis_sub_roi_state == VisSubRoiState(
            enabled=False,
            bounds=None,
            outside_opacity=DEFAULT_OUTSIDE_OPACITY,
        )

    def test_preserves_colormap_opacity_and_in_place_frame_updates(self, viewport):
        first = make_grid(5)
        first.point_data["values"] = np.full(first.n_points, 1.0)
        viewport.show_volume(first, reset_camera=False)
        viewport.set_colormap("viridis")
        viewport.set_volume_opacity(2.0)
        viewport.set_vis_sub_roi_bounds((1.0, 3.0, 1.0, 3.0, 1.0, 3.0))
        viewport.set_vis_sub_roi_enabled(True)

        cached_grid = viewport._volume_grid
        prop = viewport.plotter.actors["volume"].prop
        expected_unit_dist = prop.opacity_unit_distance

        second = make_grid(5)
        second.point_data["values"] = np.full(second.n_points, 3.0)
        viewport.show_volume(second, reset_camera=False, force_update=False)

        assert viewport._volume_grid is cached_grid
        np.testing.assert_allclose(viewport._volume_grid.point_data["values"], 3.0)
        assert prop.opacity_unit_distance == pytest.approx(expected_unit_dist)
        assert np.allclose(lut_colors(viewport), colormap_colors("viridis"))


class TestViewportBlobsAndTrajectoriesSubRoi:
    @staticmethod
    def _sample_blobs() -> tuple[pd.DataFrame, pv.PolyData]:
        df = pd.DataFrame(
            {
                "frame": [0, 0, 0],
                "label": [1, 2, 3],
                "x_um": [2.0, 4.0, 9.0],
                "y_um": [2.0, 4.0, 2.0],
                "z_um": [2.0, 2.0, 2.0],
                "volume_um3": [12.0, 14.0, 16.0],
            }
        )
        return df, create_blob_mesh(df)

    @staticmethod
    def _sample_trajectories(
        color_mode: TrajectoryColorMode = TrajectoryColorMode.SPEED,
        colormap: str = "viridis",
        tail_length: int = -1,
    ) -> tuple[PreparedTrajectories, pv.PolyData]:
        df = pd.DataFrame(
            {
                "track_id": [1, 1, 2, 2, 3, 3],
                "frame": [0, 1, 0, 1, 0, 1],
                "x_um": [0.0, 10.0, 2.0, 3.0, 7.0, 9.0],
                "y_um": [2.0, 2.0, 2.0, 2.0, 8.0, 8.0],
                "z_um": [2.0, 2.0, 2.0, 2.0, 2.0, 2.0],
                "t_s": [0.0, 1.0, 0.0, 1.0, 0.0, 1.0],
            }
        )
        prepared = PreparedTrajectories.from_dataframe(df)
        cfg = TrajectoryRenderConfig(color_mode=color_mode, colormap=colormap, tail_length=tail_length)
        return prepared, build_trajectory_polydata(prepared, current_frame=1, config=cfg)

    def test_blobs_sub_roi_updates_rgba_in_place_and_preserves_actor_visibility_and_source(self, viewport):
        df, src_poly = self._sample_blobs()
        df_before = df.copy(deep=True)
        src_pts_before = np.asarray(src_poly.points).copy()

        viewport.show_blobs(src_poly)
        blobs_actor = viewport.plotter.actors["blobs"]
        assert "rgba" not in src_poly.point_data
        assert len(viewport.plotter.scalar_bars) == 0

        # Initially inactive -> all blobs opaque red
        assert viewport._blobs_poly is not None
        np.testing.assert_array_equal(
            viewport._blobs_poly.point_data["rgba"],
            np.array([[*DEFAULT_BLOB_RGB, 255]] * 3, dtype=np.uint8),
        )

        # Hide blobs and verify Sub-ROI updates keep actor reused and hidden
        viewport.set_blobs_visible(False)
        viewport.set_vis_sub_roi_bounds((1.0, 4.0, 1.0, 4.0, 1.0, 4.0))
        viewport.set_vis_sub_roi_enabled(True)

        assert viewport.plotter.actors["blobs"] is blobs_actor
        assert blobs_actor.GetVisibility() == 0
        np.testing.assert_array_equal(
            viewport._blobs_poly.point_data["rgba"][:, :3],
            np.tile(DEFAULT_BLOB_RGB, (3, 1)),
        )
        np.testing.assert_array_equal(
            viewport._blobs_poly.point_data["rgba"][:, 3],
            np.array([255, 255, 3], dtype=np.uint8),
        )

        # Update outside opacity and re-show blobs
        viewport.set_vis_sub_roi_outside_opacity(0.25)
        viewport.set_blobs_visible(True)
        assert viewport.plotter.actors["blobs"] is blobs_actor
        assert blobs_actor.GetVisibility() == 1
        assert viewport._blobs_poly.point_data["rgba"][2, 3] == round(0.25 * 255)

        # Disabling restores full opacity while preserving bounds & outside_opacity
        viewport.set_vis_sub_roi_enabled(False)
        assert viewport.plotter.actors["blobs"] is blobs_actor
        np.testing.assert_array_equal(
            viewport._blobs_poly.point_data["rgba"][:, 3],
            np.array([255, 255, 255], dtype=np.uint8),
        )

        # Re-enabling then clear_vis_sub_roi restores full opacity and preserves outside_opacity
        viewport.set_vis_sub_roi_enabled(True)
        assert viewport._blobs_poly.point_data["rgba"][2, 3] == round(0.25 * 255)
        viewport.clear_vis_sub_roi()
        np.testing.assert_array_equal(
            viewport._blobs_poly.point_data["rgba"][:, 3],
            np.array([255, 255, 255], dtype=np.uint8),
        )
        assert viewport.vis_sub_roi_state.outside_opacity == pytest.approx(0.25)

        # Mutating live display poly must not mutate caller source or internal source copy
        viewport._blobs_poly.points[0, 0] = -999.0
        pd.testing.assert_frame_equal(df, df_before)
        np.testing.assert_array_equal(src_poly.points, src_pts_before)
        assert "rgba" not in src_poly.point_data
        assert viewport._blobs_source_poly is not None
        assert viewport._blobs_source_poly.points[0, 0] == pytest.approx(2.0)

    def test_trajectories_sub_roi_splits_reuses_actor_preserves_line_width_rgb_and_restores(self, viewport):
        prepared, src_poly = self._sample_trajectories(
            color_mode=TrajectoryColorMode.SPEED,
            colormap="viridis",
        )
        src_pts_before = np.asarray(src_poly.points).copy()
        src_rgb_before = np.asarray(src_poly.point_data["rgb"]).copy()
        src_lines_before = np.asarray(src_poly.lines).copy()
        prepared_pts_before = prepared.points_um.copy()

        viewport.show_trajectories(src_poly, line_width=4.25)
        tracks_actor = viewport.plotter.actors["tracks_highlighted"]
        assert len(viewport.plotter.scalar_bars) == 0
        assert viewport._trajectories_poly is not None
        assert viewport._trajectories_poly.n_points == src_poly.n_points
        assert viewport._trajectories_poly.n_cells == src_poly.n_cells
        np.testing.assert_array_equal(viewport._trajectories_poly.point_data["rgba"][:, :3], src_rgb_before)
        np.testing.assert_array_equal(
            viewport._trajectories_poly.point_data["rgba"][:, 3],
            np.full(src_poly.n_points, 255, dtype=np.uint8),
        )

        # Enable Sub-ROI: Track 1 crosses x=1 and x=5 (3 segments), Track 2 inside, Track 3 outside
        viewport.set_vis_sub_roi_bounds((1.0, 5.0, 1.0, 5.0, 1.0, 5.0))
        viewport.set_vis_sub_roi_outside_opacity(0.01)
        viewport.set_vis_sub_roi_enabled(True)

        assert viewport.plotter.actors["tracks_highlighted"] is tracks_actor
        assert tracks_actor.GetProperty().GetLineWidth() == pytest.approx(4.25)
        assert viewport._trajectories_poly.n_cells == 5  # 3 (Track 1) + 1 (Track 2) + 1 (Track 3)

        tids = viewport._trajectories_poly.point_data["track_id"]
        alphas = viewport._trajectories_poly.point_data["rgba"][:, 3]
        assert np.all(alphas[tids == 2] == 255)
        assert np.all(alphas[tids == 3] == 3)
        assert set(alphas[tids == 1].tolist()) == {3, 255}

        # Disabling restores exact original unsplit geometry, RGB, and full opacity
        viewport.set_vis_sub_roi_enabled(False)
        assert viewport.plotter.actors["tracks_highlighted"] is tracks_actor
        assert tracks_actor.GetProperty().GetLineWidth() == pytest.approx(4.25)
        assert viewport._trajectories_poly.n_points == src_poly.n_points
        assert viewport._trajectories_poly.n_cells == src_poly.n_cells
        np.testing.assert_array_equal(viewport._trajectories_poly.lines, src_lines_before)
        np.testing.assert_array_equal(viewport._trajectories_poly.point_data["rgba"][:, :3], src_rgb_before)
        np.testing.assert_array_equal(
            viewport._trajectories_poly.point_data["rgba"][:, 3],
            np.full(src_poly.n_points, 255, dtype=np.uint8),
        )

        # Source PolyData and PreparedTrajectories are never mutated
        assert "rgba" not in src_poly.point_data
        np.testing.assert_array_equal(src_poly.points, src_pts_before)
        np.testing.assert_array_equal(src_poly.point_data["rgb"], src_rgb_before)
        np.testing.assert_array_equal(prepared.points_um, prepared_pts_before)

    def test_showing_blobs_and_trajectories_while_sub_roi_already_enabled_applies_immediately(self, viewport):
        viewport.set_vis_sub_roi_bounds((1.0, 5.0, 1.0, 5.0, 1.0, 5.0))
        viewport.set_vis_sub_roi_outside_opacity(0.2)
        viewport.set_vis_sub_roi_enabled(True)

        _, blobs_poly = self._sample_blobs()
        _, tracks_poly = self._sample_trajectories(color_mode=TrajectoryColorMode.TRACK_ID)

        viewport.show_blobs(blobs_poly)
        viewport.show_trajectories(tracks_poly, line_width=3.5)

        expected_out_alpha = round(0.2 * 255)
        assert viewport._blobs_poly is not None
        np.testing.assert_array_equal(
            viewport._blobs_poly.point_data["rgba"][:, 3],
            np.array([255, 255, expected_out_alpha], dtype=np.uint8),
        )
        assert viewport._trajectories_poly is not None
        assert viewport._trajectories_poly.n_cells == 5
        assert viewport.plotter.actors["tracks_highlighted"].GetProperty().GetLineWidth() == pytest.approx(
            3.5
        )

        viewport.clear()
        assert viewport._blobs_source_poly is None
        assert viewport._trajectories_source_poly is None
        assert viewport.vis_sub_roi_state == VisSubRoiState(
            enabled=False,
            bounds=None,
            outside_opacity=DEFAULT_OUTSIDE_OPACITY,
        )


class TestViewportVisSubRoiInteraction:
    @staticmethod
    def _setup_front_camera(viewport: Viewport) -> None:
        viewport.resize(600, 600)
        viewport.plotter.render_window.SetSize(600, 600)
        viewport.show_volume(make_grid(), reset_camera=True)
        viewport.plotter.camera.SetPosition(2.0, 2.0, 20.0)
        viewport.plotter.camera.SetFocalPoint(2.0, 2.0, 2.0)
        viewport.plotter.camera.SetViewUp(0.0, 1.0, 0.0)
        viewport.plotter.renderer.ResetCameraClippingRange()

    @staticmethod
    def _world_to_px(viewport: Viewport, wx: float, wy: float, wz: float) -> tuple[int, int]:
        renderer = viewport.plotter.renderer
        renderer.SetWorldPoint(wx, wy, wz, 1.0)
        renderer.WorldToDisplay()
        dx, dy, _ = renderer.GetDisplayPoint()
        return int(round(dx)), int(round(dy))

    # we test the signal emission in two cases: when a new grid is shown
    # and when the existing grid is updated in place
    # protect from identical bounds when we close and open a file with same grid size
    def test_displayed_volume_bounds_updated_emits_on_new_grid_and_in_place_fast_path(self, viewport):
        received: list[tuple[float, float, float, float, float, float]] = []
        viewport.displayed_volume_bounds_updated.connect(received.append)

        first = make_grid(5)
        first.point_data["values"] = np.full(first.n_points, 1.0)
        viewport.show_volume(first, reset_camera=False)
        cached_grid = viewport._volume_grid

        second = make_grid(5)
        second.point_data["values"] = np.full(second.n_points, 2.0)
        viewport.show_volume(second, reset_camera=False, force_update=False)

        assert viewport._volume_grid is cached_grid
        assert len(received) == 2
        assert received[0] == pytest.approx((0.0, 4.0, 0.0, 4.0, 0.0, 4.0))
        assert received[1] == pytest.approx((0.0, 4.0, 0.0, 4.0, 0.0, 4.0))

    # if no volume displayed yet, the signal should not be emitted
    def test_start_vis_sub_roi_selection_ignored_without_volume(self, viewport):
        started: list[bool] = []
        viewport.vis_sub_roi_selection_started.connect(lambda: started.append(True))

        viewport.start_vis_sub_roi_selection()

        assert viewport.vis_sub_roi_mode == VisSubRoiMode.INACTIVE
        assert started == []

    # simulate all click-drag-release events to create a sub-ROI
    # and verify the box widget is enabled
    def test_click_drag_release_creates_vis_sub_roi_and_enables_separate_box_widget(self, viewport):
        self._setup_front_camera(viewport)
        started: list[bool] = []
        bounds_updates: list[tuple[float, float, float, float, float, float]] = []
        viewport.vis_sub_roi_selection_started.connect(lambda: started.append(True))
        viewport.vis_sub_roi_bounds_changed.connect(bounds_updates.append)

        viewport.set_vis_sub_roi_outside_opacity(0.05)
        viewport.start_vis_sub_roi_selection()
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.WAITING_FIRST_POINT
        assert len(started) == 1

        iren = viewport.plotter.iren.interactor

        # Click outside volume stays in WAITING_FIRST_POINT
        iren.SetEventPosition(1, 1)
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.WAITING_FIRST_POINT

        # Click inside volume and drag across the front face
        iren.SetEventPosition(*self._world_to_px(viewport, 1.0, 1.0, 4.0))
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.DRAGGING
        assert viewport.roi_mode == RoiMode.INACTIVE

        iren.SetEventPosition(*self._world_to_px(viewport, 3.0, 3.0, 4.0))
        viewport._on_mouse_move(None, "MouseMoveEvent")

        assert "vis_sub_roi_preview" in viewport.plotter.actors
        assert "roi_preview" not in viewport.plotter.actors
        assert viewport.vis_sub_roi_state.enabled is True
        assert viewport.vis_sub_roi_state.outside_opacity == pytest.approx(0.05)
        assert viewport.vis_sub_roi_state.bounds is not None
        np.testing.assert_allclose(
            viewport.vis_sub_roi_state.bounds,
            (1.0, 3.0, 1.0, 3.0, 0.0, 4.0),
            atol=0.25,
        )

        # Release transitions to EDITING with dedicated axis-aligned box widget
        viewport._on_left_button_release(None, "LeftButtonReleaseEvent")
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.EDITING
        assert viewport.vis_sub_roi_box_visible is True
        assert viewport._vis_sub_roi_box_widget is not None
        assert viewport._vis_sub_roi_box_widget.GetEnabled() == 1
        assert viewport._vis_sub_roi_box_widget.GetRotationEnabled() == 0
        assert viewport._roi_box_widget is None
        assert len(bounds_updates) >= 2

    # simulate a quick click without any mouse move to create a sub-ROI
    # and verify the box widget is enabled
    def test_quick_click_without_mouse_move_creates_vis_sub_roi_on_release(self, viewport):
        self._setup_front_camera(viewport)
        viewport.start_vis_sub_roi_selection()

        iren = viewport.plotter.iren.interactor
        iren.SetEventPosition(*self._world_to_px(viewport, 2.0, 2.0, 4.0))
        viewport._on_left_button_press(None, "LeftButtonPressEvent")
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.DRAGGING

        viewport._on_left_button_release(None, "LeftButtonReleaseEvent")
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.EDITING
        assert viewport.vis_sub_roi_state.enabled is True
        assert viewport.vis_sub_roi_state.bounds is not None
        assert viewport.vis_sub_roi_box_visible is True

    # simulate a click-drag-release to create a sub-ROI, then resize and translate the box widget
    # and verify the bounds are clamped to the volume and the enabled flag is preserved
    def test_box_widget_resize_and_translation_clamp_and_preserve_enabled_flag(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=True)  # bounds 0..4
        viewport.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=True,
                bounds=(1.0, 3.0, 1.0, 3.0, 1.0, 3.0),
                outside_opacity=0.15,
            )
        )
        viewport.show_vis_sub_roi_box()
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.EDITING
        assert viewport._vis_sub_roi_box_rep is not None

        updates: list[tuple[float, float, float, float, float, float]] = []
        viewport.vis_sub_roi_bounds_changed.connect(updates.append)

        # Resize X min past 0.0 -> must clamp to 0.0
        viewport._on_vis_sub_roi_box_start_interaction(None, "StartInteractionEvent")
        viewport._vis_sub_roi_box_rep.PlaceWidget([-4.0, 3.0, 1.0, 3.0, 1.0, 3.0])
        viewport._on_vis_sub_roi_box_interaction(None, "InteractionEvent")
        viewport._on_vis_sub_roi_box_end_interaction(None, "EndInteractionEvent")

        assert viewport.vis_sub_roi_state.bounds == pytest.approx((0.0, 3.0, 1.0, 3.0, 1.0, 3.0))
        assert viewport.vis_sub_roi_state.enabled is True
        assert viewport.vis_sub_roi_state.outside_opacity == pytest.approx(0.15)
        assert len(updates) == 1

        # Pure translation past +X edge -> slides to [1.0, 4.0] keeping width 3.0
        viewport._on_vis_sub_roi_box_start_interaction(None, "StartInteractionEvent")
        b = viewport._vis_sub_roi_box_rep.GetBounds()
        viewport._vis_sub_roi_box_rep.PlaceWidget([b[0] + 5.0, b[1] + 5.0, b[2], b[3], b[4], b[5]])
        viewport._on_vis_sub_roi_box_interaction(None, "InteractionEvent")
        viewport._on_vis_sub_roi_box_end_interaction(None, "EndInteractionEvent")

        assert viewport.vis_sub_roi_state.bounds == pytest.approx((1.0, 4.0, 1.0, 3.0, 1.0, 3.0))

    # test that stop_vis_sub_roi_interaction, clear_vis_sub_roi,
    # and reset_vis_sub_roi_state have distinct semantics
    def test_stop_interaction_clear_and_reset_keep_distinct_semantics(self, viewport):
        viewport.show_volume(make_grid(), reset_camera=False)
        ended: list[bool] = []
        viewport.vis_sub_roi_interaction_ended.connect(lambda: ended.append(True))

        # Calling stop when already inactive is a quiet no-op
        viewport.stop_vis_sub_roi_interaction()
        assert ended == []

        viewport.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=True,
                bounds=(1.0, 3.0, 1.0, 3.0, 1.0, 3.0),
                outside_opacity=0.2,
            )
        )
        viewport.set_vis_sub_roi_box_visible(True)
        assert viewport.vis_sub_roi_box_visible is True

        # stop_vis_sub_roi_interaction hides box but preserves visualization state
        viewport.stop_vis_sub_roi_interaction()
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.INACTIVE
        assert viewport.vis_sub_roi_box_visible is False
        assert len(ended) == 1
        assert viewport.vis_sub_roi_state == VisSubRoiState(
            enabled=True,
            bounds=(1.0, 3.0, 1.0, 3.0, 1.0, 3.0),
            outside_opacity=0.2,
        )

        # clear_vis_sub_roi hides box, disables and clears bounds, preserves outside_opacity
        viewport.show_vis_sub_roi_box()
        viewport.clear_vis_sub_roi()
        assert viewport.vis_sub_roi_box_visible is False
        assert viewport.vis_sub_roi_state == VisSubRoiState(
            enabled=False,
            bounds=None,
            outside_opacity=0.2,
        )

        # reset_vis_sub_roi_state resets outside_opacity back to 0.01 without removing volume
        viewport.set_vis_sub_roi_state(
            VisSubRoiState(enabled=True, bounds=(1.0, 3.0, 1.0, 3.0, 1.0, 3.0), outside_opacity=0.3)
        )
        viewport.show_vis_sub_roi_box()
        viewport.reset_vis_sub_roi_state()
        assert viewport.vis_sub_roi_box_visible is False
        assert "volume" in viewport.plotter.actors
        assert viewport.vis_sub_roi_state == VisSubRoiState(
            enabled=False,
            bounds=None,
            outside_opacity=DEFAULT_OUTSIDE_OPACITY,
        )

    # test that starting a DATA_ROI selection hides the VIS_SUB_ROI box,
    # and starting a VIS_SUB_ROI selection cancels any active DATA_ROI preview
    def test_mutual_exclusion_with_data_roi_and_reclamping_on_new_grid(self, viewport):
        viewport.show_volume(make_grid(6), reset_camera=False)  # bounds 0..5
        viewport.set_vis_sub_roi_state(
            VisSubRoiState(enabled=True, bounds=(1.0, 4.5, 1.0, 4.5, 1.0, 4.5), outside_opacity=0.05)
        )
        viewport.show_vis_sub_roi_box()
        assert viewport.vis_sub_roi_box_visible is True

        # Starting DATA_ROI hides VIS_SUB_ROI box without altering VIS_SUB_ROI state
        viewport.start_roi_selection()
        assert viewport.roi_mode == RoiMode.WAITING_FIRST_POINT
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.INACTIVE
        assert viewport.vis_sub_roi_box_visible is False
        assert viewport.vis_sub_roi_state.bounds == pytest.approx((1.0, 4.5, 1.0, 4.5, 1.0, 4.5))

        # show_vis_sub_roi_box is ignored while DATA_ROI is active
        viewport.show_vis_sub_roi_box()
        assert viewport.vis_sub_roi_box_visible is False

        # Starting VIS_SUB_ROI selection defensively cancels active DATA_ROI preview
        viewport.set_roi_preview(RegionOfInterest(0.5, 3.0, 0.5, 3.0, 0.5, 3.0))
        assert viewport.roi_mode == RoiMode.EDITING
        viewport.start_vis_sub_roi_selection()
        assert viewport.roi_mode == RoiMode.INACTIVE
        assert "roi_preview" not in viewport.plotter.actors
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.WAITING_FIRST_POINT

        # Showing a smaller volume re-clamps an already-visible VIS_SUB_ROI editing box
        viewport.stop_vis_sub_roi_interaction()
        viewport.show_vis_sub_roi_box((1.0, 4.5, 1.0, 4.5, 1.0, 4.5))
        viewport.show_volume(make_grid(4), reset_camera=False)  # bounds 0..3
        assert viewport._vis_sub_roi_box_rep is not None
        box_bounds = viewport._vis_sub_roi_box_rep.GetBounds()
        assert box_bounds[1] <= 3.0
        assert box_bounds[3] <= 3.0
        assert box_bounds[5] <= 3.0

        viewport.clear()
        assert viewport.vis_sub_roi_mode == VisSubRoiMode.INACTIVE
        assert viewport._vis_sub_roi_box_widget is not None
        assert viewport._vis_sub_roi_box_widget.GetEnabled() == 0


class TestViewportVelocityScalarBar:
    def test_switch_to_velocity_bar_is_isolated_from_volume_updates_and_restores_cleanly(self, viewport):
        first = make_grid(5)
        first.point_data["values"] = np.linspace(0.0, 100.0, first.n_points)
        viewport.show_volume(first, reset_camera=False)
        assert viewport.scalar_bar_mode == ScalarBarMode.VOLUME
        assert "values" in viewport.plotter.scalar_bars

        title = "Velocity (µm/s)"
        viewport.show_velocity_scalar_bar(0.0, 42.5, "turbo", visible=True, title=title)

        assert viewport.scalar_bar_mode == ScalarBarMode.VELOCITY
        assert "values" not in viewport.plotter.scalar_bars
        assert title in viewport.plotter.scalar_bars
        vel_bar = viewport.plotter.scalar_bars[title]
        assert vel_bar.GetVisibility() == 1
        vel_lut = vel_bar.GetLookupTable()
        assert vel_lut is not viewport.plotter.actors["volume"].mapper.lookup_table
        assert vel_lut.GetTableRange() == pytest.approx((0.0, 42.5))

        # Volume updates (in-place fast path and new grid) and colormap changes must not restore "values"
        second = make_grid(5)
        second.point_data["values"] = np.linspace(10.0, 500.0, second.n_points)
        viewport.show_volume(second, reset_camera=False, force_update=False)
        viewport.show_volume(make_grid(7), reset_camera=False, force_update=True)
        viewport.set_colormap("viridis")

        assert "values" not in viewport.plotter.scalar_bars
        assert title in viewport.plotter.scalar_bars
        assert viewport.plotter.scalar_bars[title].GetLookupTable().GetTableRange() == pytest.approx(
            (0.0, 42.5)
        )

        # Hiding/showing and updating colormap/text color work in-place
        viewport.show_velocity_scalar_bar(0.0, 42.5, "plasma", visible=False, title=title)
        assert viewport.plotter.scalar_bars[title].GetVisibility() == 0
        assert "values" not in viewport.plotter.scalar_bars

        viewport.show_velocity_scalar_bar(0.0, 55.0, "viridis", visible=True, title=title)
        assert viewport.plotter.scalar_bars[title].GetVisibility() == 1
        assert viewport.plotter.scalar_bars[title].GetLookupTable().GetTableRange() == pytest.approx(
            (0.0, 55.0)
        )
        viewport.set_text_color("white")
        assert viewport.plotter.scalar_bars[title].GetTitleTextProperty().GetColor() == pytest.approx(
            (1.0, 1.0, 1.0)
        )

        # Restoring volume scalar bar removes velocity bar and brings back "values" tied to volume LUT
        viewport.restore_volume_scalar_bar()
        assert viewport.scalar_bar_mode == ScalarBarMode.VOLUME
        assert title not in viewport.plotter.scalar_bars
        assert "values" in viewport.plotter.scalar_bars
        assert (
            viewport.plotter.scalar_bars["values"].GetLookupTable()
            is viewport.plotter.actors["volume"].mapper.lookup_table
        )

    def test_scalar_bar_visibility_toggle_applies_to_velocity_bar_and_preserves_layer_state(self, viewport):
        viewport.show_volume(make_grid(5), reset_camera=False)
        viewport.show_velocity_scalar_bar(0.0, 42.5, "turbo", visible=True, title="Velocity")
        velocity_bar = viewport.plotter.scalar_bars["Velocity"]

        viewport.set_scalar_bar_visible(False)
        assert velocity_bar.GetVisibility() == 0

        viewport.show_velocity_scalar_bar(0.0, 42.5, "turbo", visible=True, title="Velocity")
        assert velocity_bar.GetVisibility() == 0

        viewport.set_scalar_bar_visible(True)
        assert velocity_bar.GetVisibility() == 1

        viewport.show_velocity_scalar_bar(0.0, 42.5, "turbo", visible=False, title="Velocity")
        viewport.set_scalar_bar_visible(False)
        viewport.set_scalar_bar_visible(True)
        assert velocity_bar.GetVisibility() == 0

        viewport.restore_volume_scalar_bar()
        assert viewport.plotter.scalar_bars["values"].GetVisibility() == 1

    def test_volume_frame_update_and_colormap_survive_after_velocity_bar_and_trajectories_gc(self, viewport):
        first = make_grid(5)
        first.point_data["values"] = np.linspace(0.0, 100.0, first.n_points)
        viewport.show_volume(first, reset_camera=False)

        pts = np.array([[0.0, 0.0, 0.0], [2.0, 2.0, 2.0]], dtype=np.float32)
        poly = pv.PolyData(pts, lines=np.array([2, 0, 1], dtype=np.int64))
        poly.point_data["rgb"] = np.array([[255, 0, 0], [0, 255, 0]], dtype=np.uint8)
        viewport.show_trajectories(poly)
        viewport.show_velocity_scalar_bar(0.0, 25.0, "turbo", visible=True, title="Velocity (µm/s)")

        gc.collect()

        # Advancing frame on fast path, changing volume colormap, and restoring "values" must not raise
        second = make_grid(5)
        second.point_data["values"] = np.linspace(5.0, 200.0, second.n_points)
        viewport.show_volume(second, reset_camera=False, force_update=False)
        viewport.set_colormap("viridis")
        viewport.restore_volume_scalar_bar()

        assert "values" in viewport.plotter.scalar_bars

    def test_clear_resets_scalar_bar_mode_to_volume(self, viewport):
        viewport.show_volume(make_grid(5), reset_camera=False)
        viewport.show_velocity_scalar_bar(0.0, 10.0, "turbo", visible=True, title="Velocity (µm/s)")

        viewport.clear()
        assert viewport.scalar_bar_mode == ScalarBarMode.VOLUME

        viewport.show_volume(make_grid(5), reset_camera=False)
        assert "values" in viewport.plotter.scalar_bars
