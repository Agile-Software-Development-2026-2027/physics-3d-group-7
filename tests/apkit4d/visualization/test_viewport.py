import numpy as np
import pytest
import pyvista as pv

from apkit4d.roi import RegionOfInterest
from apkit4d.visualization.viewport import (
    DEFAULT_COLORMAP,
    FAST_SCROLL_THRESHOLD,
    FULL_QUALITY_DELAY,
    MOVING_IMAGE_SAMPLE_DISTANCE,
    RoiMode,
    Viewport,
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
