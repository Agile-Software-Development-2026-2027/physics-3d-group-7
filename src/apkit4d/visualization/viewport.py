import time
from enum import Enum, auto

import numpy as np
import pyvista as pv
from matplotlib import colormaps
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget
from pyvistaqt import QtInteractor
from vtkmodules.vtkCommonCore import vtkCommand
from vtkmodules.vtkInteractionWidgets import vtkBoxRepresentation, vtkBoxWidget2

from apkit4d.roi import RegionOfInterest

"""
    in this file we define the viewport class, that is the widget that will be placed 
    at the center of the main window to visualize the 3D data.

    it is a subclass of Qwidget and it contains the QtInteractor that is used to interact with the 3D data.

"""

type Vec3D = np.ndarray[tuple[int], np.dtype[np.float64]]
type Bounds6D = tuple[float, float, float, float, float, float]

# two wheel steps closer than this (in seconds) are a fast scroll, and the zoom step grows
FAST_SCROLL_THRESHOLD = 0.12

# when the wheel stops for this long (in seconds) the view is drawn again at full quality.
# it must stay above FAST_SCROLL_THRESHOLD, otherwise during a fast scroll a full quality frame
# could be drawn between two steps
FULL_QUALITY_DELAY = 0.2

# while the view moves the volume is drawn with one ray every 2x2 pixels, scaled up to the whole view.
# it is about 2 times faster when zoomed in and the blobs keep their shape, only a bit softer
MOVING_IMAGE_SAMPLE_DISTANCE = 2.0

# how the view looks until the user changes it from the left panel
DEFAULT_COLORMAP = "inferno"
DEFAULT_VOLUME_OPACITY = 1.0
DEFAULT_BACKGROUND = "gray"
DEFAULT_OUTLINE_COLOR = "white"
DEFAULT_TEXT_COLOR = "black"


class RoiMode(Enum):
    INACTIVE = auto()
    WAITING_FIRST_POINT = auto()
    DRAGGING = auto()
    EDITING = auto()


class Viewport(QWidget):
    # signals emitted in the Roi selection
    roi_selection_started = Signal()
    roi_updated = Signal(object)
    roi_accepted = Signal(object)
    roi_cancelled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)

        # Set up the vertical layout for the widget
        self.main_layout = QVBoxLayout(self)

        self._volume_grid: pv.ImageData | None = None

        self._blobs_poly: pv.PolyData | None = None

        # Set the margins to 0 so that we use the entire space
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # that's the interactor we were talking about and here we add it to the layout
        # auto_update is off: by default pyvistaqt redraws the view 5 times a second even when
        # nothing changes, which keeps a weak GPU always busy. so the view is not redrawn by itself:
        # after changing the scene from the code (actors, opacity, colors, camera...) we must call
        # self._request_render(), as the methods below do, or the old frame stays on screen
        # until the mouse moves the view
        self.plotter = QtInteractor(self, auto_update=False)
        self.main_layout.addWidget(self.plotter.interactor)

        # set up of some viewport things
        self.plotter.set_background(DEFAULT_BACKGROUND)
        self.plotter.add_axes()
        self.plotter.enable_terrain_style()
        self.min_zoom_dist: float = 0.0
        self.max_zoom_dist: float = float("inf")

        # we store the center and bounds
        self.volume_center: np.ndarray[tuple[int], np.dtype[np.float64]] | None = None
        self.volume_bounds: Bounds6D | None = None

        # the look of the volume chosen by the user. we keep it here because a volume of another size
        # is added again from scratch, and without these it would go back to the defaults
        self._colormap: str = DEFAULT_COLORMAP
        self._volume_opacity: float = DEFAULT_VOLUME_OPACITY
        self._outline_color: str = DEFAULT_OUTLINE_COLOR
        self._text_color: str = DEFAULT_TEXT_COLOR
        # opacity unit distance that PyVista gives to the volume, set_volume_opacity scales it
        self._base_opacity_unit_distance: float = 1.0

        # they are used in the zoom acceleration function
        self.last_zoom_time: float = 0.0
        self.current_zoom_factor: float = 0.01

        # state for the ROI selection
        self._roi_mode: RoiMode = RoiMode.INACTIVE
        self._roi_start_point: Vec3D | None = None
        self._current_roi: RegionOfInterest | None = None
        self._roi_box_poly: pv.PolyData | None = None

        """
            i'll use vtkBoxWidget2 and vtkBoxRepresentation to show the ROI as a 3D box 
            with handles that can be dragged to modify it. we will have 6 handels + 1
            at the center to drag the entire box
        """
        self._roi_box_rep: vtkBoxRepresentation | None = None
        self._roi_box_widget: vtkBoxWidget2 | None = None

        iren = self.plotter.iren.interactor  # vtkRenderWindowInteractor

        # disable the default zoom so i can implement mine.
        # _stop_wheel_event already stops the wheel event before the default zoom, the factor at 0
        # is kept on purpose as a second guard
        style = iren.GetInteractorStyle()
        if style is not None:
            style.SetMouseWheelMotionFactor(0.0)

        for event in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent"):
            iren.AddObserver(event, self._update_zoom_acceleration, 10.0)

        # observers for the zoom events with a lower priority than acceleration, so that
        # the acceleration is updated first
        self._wheel_forward_tag = iren.AddObserver(
            "MouseWheelForwardEvent", self._on_mouse_wheel_forward, 5.0
        )
        self._wheel_backward_tag = iren.AddObserver(
            "MouseWheelBackwardEvent", self._on_mouse_wheel_backward, 5.0
        )

        # while the wheel turns the view is drawn at the lower quality used for moving cameras,
        # when it stops for FULL_QUALITY_DELAY it is drawn once at full quality
        self._full_quality_timer = QTimer(self)
        self._full_quality_timer.setSingleShot(True)
        self._full_quality_timer.setInterval(round(FULL_QUALITY_DELAY * 1000))
        self._full_quality_timer.timeout.connect(self._request_full_quality_render)

        # before every redraw the quality of the volume is chosen, see _set_volume_quality
        render_window = self.plotter.render_window
        if render_window is not None:
            render_window.AddObserver("StartEvent", self._set_volume_quality)

        # the wheel events are not here: _stop_wheel_event stops them before they get to this observer,
        # so the wheel zoom is kept inside the limits by the clamp in compute_local_zoom_step
        for event in ("InteractionEvent", "EndInteractionEvent"):
            iren.AddObserver(event, self._limit_zoom, -1.0)

        # observers for the ROI selection, they have a high priority
        # so that we can block the rotation of the camera
        self._left_press_tag = iren.AddObserver("LeftButtonPressEvent", self._on_left_button_press, 10.0)
        self._mouse_move_tag = iren.AddObserver("MouseMoveEvent", self._on_mouse_move, 10.0)
        self._left_release_tag = iren.AddObserver(
            "LeftButtonReleaseEvent", self._on_left_button_release, 10.0
        )

        # TODO: the next step is also deactivating the default panning and maybe implement a custom one

    def show_volume(self, grid: pv.ImageData, reset_camera: bool = True) -> None:
        """
        This function is used to visualize the 3D data in the viewport.

        Parameters:
            grid (pv.ImageData): PyVista ImageData object that we mapped in the data_mapper.py file.
            it contains the 3D data that we want to visualize.

        Returns:
            None
        """
        if grid is None or grid.n_points == 0:
            return

        # with this if we want to avoid to recreate the volume when we will change frames
        # we just update the values
        if (
            self._volume_grid is not None
            and self._volume_grid.dimensions == grid.dimensions
            and self._volume_grid.spacing == grid.spacing
            and self._volume_grid.origin == grid.origin
        ):
            # "values" is the name of the point data we used in the data_mapper.py file
            # it represents the 3D data in a flattened format, which is the intensity
            # values of the voxels
            # I don't know if replace this with .active_scalars so that if we change the
            # name in the mapper we don't have to change it here too,
            # but for now we keep it as it is
            values = grid.point_data["values"]
            np.copyto(self._volume_grid.point_data["values"], values)

            # fixed the bug of blobs not moving caused by the missing call on
            # .Modified() on the scalars and the point data, that was needed to tell
            #  VTK that the data has changed
            self._volume_grid.GetPointData().GetScalars().Modified()
            self._volume_grid.point_data.Modified()
            self._volume_grid.Modified()

            # Aggiorna il range min, max della colormap/opacità e della scalar bar
            vmin, vmax = float(np.min(values)), float(np.max(values))
            self.plotter.actors["volume"].mapper.scalar_range = (vmin, vmax)
            self.plotter.update_scalar_bar_range((vmin, vmax))

            if reset_camera:
                self.plotter.renderer.reset_camera(render=False)
            self._request_render()
            return

        self._volume_grid = grid.copy()

        # here we add the volume, that is the blob data
        # render=False here and below: PyVista would draw the view after each call (the scalar bar too),
        # we draw it once at the end
        actor = self.plotter.add_volume(
            self._volume_grid,
            cmap=self._colormap,
            opacity="linear",
            name="volume",
            mapper="gpu",
            render=False,
            scalar_bar_args={"render": False},
        )

        # the gpu mapper lets us draw the moving frames at a lower resolution (see _set_volume_quality),
        # the smart one (PyVista's default) does not. with the sample distance taken from the voxel
        # spacing, as the smart mapper does, the still image is the same as before
        actor.mapper.LockSampleDistanceToInputSpacingOn()

        # the new volume and its scalar bar get the opacity and the text color chosen by the user
        self._base_opacity_unit_distance = actor.prop.opacity_unit_distance
        self._apply_volume_opacity(actor)
        self._paint_text()

        # with this we can see the cube borders
        self.plotter.add_mesh(
            self._volume_grid.outline(),
            color=self._outline_color,
            line_width=2,
            name="outline",
            render=False,
        )

        # store the center and bounds
        self.volume_center = np.array(self._volume_grid.center, dtype=np.float64)
        self.volume_bounds = self._volume_grid.bounds

        # i think setting max and min zoom only the first time we show the volume or when we reset
        # should work, that kinda depends on how we are going to handle future ROIs
        if self.max_zoom_dist == float("inf") or reset_camera:
            diagonal = self._volume_grid.length
            self.min_zoom_dist = diagonal * 0.1
            self.max_zoom_dist = diagonal * 4.0

        # since we work with 4D data i've put the reset as an option, we don't want to reset on every frame,
        # but it could be useful in some cases, so we leave it as an option for now.
        # we call the reset_camera of the renderer: the one of the plotter draws the view
        # even with render=False
        if reset_camera:
            self.plotter.renderer.reset_camera(render=False)

        self._request_render()

    def set_colormap(self, name: str) -> None:
        """
        This function changes the colors of the volume. the scalar bar uses the same colors,
        so it changes too.

        Parameters:
            name (str): name of a matplotlib colormap, for example "inferno" or "viridis"

        Returns:
            None

        Raises:
            ValueError: if matplotlib has no colormap with this name
        """
        # we check the name now: a wrong one would break the next volume we add
        if name not in colormaps:
            raise ValueError(f"unknown colormap: {name}")

        self._colormap = name
        actor = self.plotter.actors.get("volume")
        if actor is not None:
            # the lookup table builds the new colors and keeps the opacity it already has
            actor.mapper.lookup_table.cmap = name
            self._request_render()

    def set_volume_opacity(self, opacity: float) -> None:
        """
        This function makes the volume more or less opaque.

        Parameters:
            opacity (float): 1.0 is the default look, 2.0 is twice as opaque, 0.5 half as opaque

        Returns:
            None

        Raises:
            ValueError: if the opacity is not greater than 0
        """
        if opacity <= 0:
            raise ValueError(f"the opacity must be greater than 0, got {opacity}")

        self._volume_opacity = opacity
        actor = self.plotter.actors.get("volume")
        if actor is not None:
            self._apply_volume_opacity(actor)
            self._request_render()

    def set_background(self, color: str) -> None:
        """
        This function changes the background color of the view.

        Parameters:
            color (str): a color name or a hex string, for example "black" or "#2b2d31"

        Returns:
            None
        """
        # the background stays when the volume is added again, so we don't need to keep it
        self.plotter.set_background(color)
        self._request_render()

    def set_outline_color(self, color: str) -> None:
        """
        This function changes the color of the lines around the volume.

        Parameters:
            color (str): a color name or a hex string, for example "white" or "#1f2328"

        Returns:
            None
        """
        self._outline_color = color
        actor = self.plotter.actors.get("outline")
        if actor is not None:
            actor.prop.color = color
            self._request_render()

    def set_text_color(self, color: str) -> None:
        """
        This function changes the color of the text of the scalar bar and of the axes,
        so that it can be read on the background.

        Parameters:
            color (str): a color name or a hex string, for example "black" or "#dcdfe4"

        Returns:
            None
        """
        self._text_color = color
        self._paint_text()
        self._request_render()

    def _apply_volume_opacity(self, actor: pv.Actor) -> None:
        """
        This function gives the volume the opacity chosen by the user.

        the opacity unit distance is how thick the volume must be to have the opacity of its colors:
        when it is smaller, the light goes through less volume and the volume looks more solid.
        so dividing it by the opacity makes the volume more opaque when the opacity grows.
        we don't touch the opacity of the colors: changing it with a list of values blanks the volume.

        Parameters:
            actor (pv.Actor): the actor of the volume

        Returns:
            None
        """
        actor.prop.opacity_unit_distance = self._base_opacity_unit_distance / self._volume_opacity

    def _paint_text(self) -> None:
        """
        This function paints the text of the scalar bar and of the axes with the text color.
        PyVista has no option to change it after they are added, so we change it on the VTK objects.

        Returns:
            None
        """
        rgb = pv.Color(self._text_color).float_rgb
        for scalar_bar in self.plotter.scalar_bars.values():
            scalar_bar.GetLabelTextProperty().SetColor(rgb)
            scalar_bar.GetTitleTextProperty().SetColor(rgb)

        axes = self.plotter.renderer.axes_actor
        if axes is not None:
            for caption in (
                axes.GetXAxisCaptionActor2D(),
                axes.GetYAxisCaptionActor2D(),
                axes.GetZAxisCaptionActor2D(),
            ):
                caption.GetCaptionTextProperty().SetColor(rgb)

    def show_blobs(self, poly: pv.PolyData) -> None:
        """
        This function is used to visualize the real blobs after the blob detection

        Parameters:
            poly (pv.PolyData): PyVista PolyData object that we mapped in the data_mapper.py file.
            it contains the data of specific blobs that we want to visualize.

        Returns:
            None
        """

        # remove past blobs if the new poly is empty, and return
        if poly is None or poly.n_points == 0:
            if "blobs" in self.plotter.actors:
                self.plotter.remove_actor("blobs", render=False)
                self._blobs_poly = None
                self._request_render()
            return

        # if the blobs are already in the plotter we just update them
        if self._blobs_poly is not None and "blobs" in self.plotter.actors:
            # i can't use np.copyto here because the number of points can change
            # shallow copy substitues the pointers to the data
            self._blobs_poly.shallow_copy(poly)
            self._blobs_poly.Modified()
            self._request_render()
            return

        # shallow copy gives me an error in the test cause of NoneType here so i use copy
        self._blobs_poly = poly.copy()
        # here we add the dectected blobs in the plotter
        self.plotter.add_mesh(
            self._blobs_poly,
            color="red",
            point_size=10.0,
            render_points_as_spheres=True,
            name="blobs",
            render=False,
        )
        self._request_render()

    def clear(self):
        """
        This function is used to clear the viewport.

        it removes all the things from the plotter and resets the camera.

        Returns:
            None
        """
        self._volume_grid = None
        self._blobs_poly = None
        self.volume_center = None
        self.volume_bounds = None
        self.min_zoom_dist = 0.0
        self.max_zoom_dist = float("inf")
        self._disable_roi_box_widget()
        self.plotter.clear()
        # the reset_camera of the renderer as in show_volume, so the view is drawn only once, below
        self.plotter.renderer.reset_camera(render=False)

        # if the wheel has just moved, the full quality redraw is still waiting on the timer:
        # we stop it and draw the empty view at full quality now
        self._full_quality_timer.stop()
        self._request_full_quality_render()

        # clear the ROI selection
        self._roi_mode = RoiMode.INACTIVE
        self._roi_start_point = None
        self._current_roi = None
        self._roi_box_poly = None
        self.unsetCursor()

    def clamp_point_to_bounds(self, point: Vec3D, bounds: Bounds6D | None) -> Vec3D:
        """
        This function is used to clamp a point to the 3d bounds of the volume, to ensure that
        the focal point of the zoom is always inside

        Parameters:
            point: the point to be clamped
            bounds: the bounds of the volume

        Returns:
            the clamped point
        """
        point = np.asarray(point, dtype=np.float64)

        # if the bounds are not set, we return the point as it is,
        # since we don't have any bounds to clamp
        if bounds is None or len(bounds) != 6:
            return point

        mins = np.array([bounds[0], bounds[2], bounds[4]], dtype=np.float64)
        maxs = np.array([bounds[1], bounds[3], bounds[5]], dtype=np.float64)
        return np.clip(point, mins, maxs)

    def clamp_camera_position(
        self, position: Vec3D, focal_point: Vec3D, min_dist: float, max_dist: float
    ) -> Vec3D:
        """
        This function is used to clamp the camera position to a certain distance
        from the focal point.

        Parameters:
            position: the current position of the camera
            focal_point: the focal point of the camera
            min_dist: the minimum distance from the focal point
            max_dist: the maximum distance from the focal point

        Returns:
            the new position of the camera clamped to the min and max distance
            from the focal point
        """

        # _limit_zoom passes already array but since this function could be useful in other context
        # i'll leave the conversion also here
        # i could also take min dist and max dist from the class but for the same reason
        # i'll leave them as parameters
        position = np.asarray(position, dtype=np.float64)
        focal_point = np.asarray(focal_point, dtype=np.float64)

        vec = position - focal_point
        dist = np.linalg.norm(vec)

        if dist == 0:
            return position

        # clip the distance to be within the min and max distance
        new_dist = np.clip(dist, min_dist, max_dist)
        return focal_point + (vec / dist) * new_dist

    def _limit_zoom(self, _obj: object, _event: str) -> None:
        """
        This function is used to limit the zoom of the camera.

        it is called while the user drags the view with the mouse and when the drag ends
        (the wheel zoom is limited in compute_local_zoom_step), it checks distance between
        camera position and focal point, it calls the clamp function and updates
        the camera position if needed.

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """

        camera = self.plotter.camera
        position = np.array(camera.GetPosition(), dtype=np.float64)
        focal_point = np.array(camera.GetFocalPoint(), dtype=np.float64)

        new_pos = self.clamp_camera_position(position, focal_point, self.min_zoom_dist, self.max_zoom_dist)

        # avoid waste of rendering if the position is the same
        if not np.allclose(new_pos, position):
            camera.SetPosition(*new_pos)
            self.plotter.renderer.ResetCameraClippingRange()
            self._request_render()

    def _update_zoom_acceleration(self, _obj: object, _event: str) -> None:
        """
        This function is used to update the zoom acceleration of the camera.
        it is called when the user zooms in or out and checks the time between
        the last zoom event and the current zoom event, and updates the zoom factor

        Parameters:
            _obj: the object that called the event
            _event: the event that was called
        Returns:
            None
        """

        now = time.perf_counter()
        dt = now - self.last_zoom_time
        self.last_zoom_time = now

        # if the user is scrolling quickly, we increase the zoom factor
        if dt < FAST_SCROLL_THRESHOLD:
            # increase the zoom factor by 50% but clamp it to a maximum of 0.35
            self.current_zoom_factor = min(self.current_zoom_factor * 1.5, 0.35)
        else:
            # factor reset
            self.current_zoom_factor = 0.01

        # second guard on the default zoom, kept on purpose (see the comment in __init__)
        style = self.plotter.iren.interactor.GetInteractorStyle()
        if style is not None:
            style.SetMouseWheelMotionFactor(0.0)

    def compute_local_zoom_step(
        self,
        position: Vec3D,
        focal_point: Vec3D,
        target_point: Vec3D,
        volume_center: Vec3D | None = None,
        direction: int = 1,
        zoom_factor: float | None = None,
        min_dist: float | None = None,
        max_dist: float | None = None,
        bounds: Bounds6D | None = None,
    ) -> tuple[Vec3D, Vec3D]:
        """
        This function is used to compute the new camera position and focal point
        for cursor-based zooming, and re-centering zoom out

        Parameters:
            position: the current position of the camera
            focal_point: the current focal point of the camera
            target_point: the point under the cursor
            volume_center: the center of the volume
            direction: 1 for zoom in, -1 for zoom out
            zoom_factor: the zoom factor to be applied for the dynamic acceleration
            min_dist: the minimum distance from the focal point
            max_dist: the maximum distance from the focal point
            bounds: optional bounds to clamp the focal point

        Returns:
            tuple containing the new camera position and focal point as numpy arrays
        """

        # if the volume center is not provided, we use the focal point as the center
        center = volume_center if volume_center is not None else focal_point

        # use self values if they are not provided
        zoom_factor = self.current_zoom_factor if zoom_factor is None else zoom_factor
        min_dist = self.min_zoom_dist if min_dist is None else min_dist
        max_dist = self.max_zoom_dist if max_dist is None else max_dist
        bounds = self.volume_bounds if bounds is None else bounds

        vec = position - focal_point
        dist = float(np.linalg.norm(vec))
        if dist == 0.0:
            return position, focal_point

        # the direction vector from the focal point to the camera position (versor)
        view_dir_from_focal = vec / dist

        # calculate the step based on the zoom factor clamped between a range
        step = float(np.clip(zoom_factor, 0.01, 0.35))

        if direction > 0:
            # zoom in
            # we divide by (1 + step) so that the more we zoom in the less we zoom
            new_dist = max(dist / (1.0 + step), min_dist)

            """
                calculate the effective alpha for focal point adjustment based on the distance 
                change. the effective alpha is a value between 0 and 1 that represents how much 
                we move the focal point towards the target point

                why we use effective alpha? Theorem of similar triangles:
                if the camera zoom towards the object reducing the distance of 20%, the field
                of view is reduced also by 20%, if we want the target point to stay under the 
                cursor the focal point must move towards the target point also by 20%

                 


            """
            effective_alpha = (dist - new_dist) / dist if dist > 0 else 0.0

            # adjust the focal point
            new_focal = focal_point + effective_alpha * (target_point - focal_point)
            if bounds is not None:
                new_focal = self.clamp_point_to_bounds(new_focal, bounds)
        else:
            # zoom out that recenters the focal point towards the center of the volume
            # inverse of the zoom in formula
            new_dist = min(dist * (1.0 + step), max_dist)

            # calculate how close we are to a global view based on the distance from the center of the volume
            if np.isfinite(max_dist) and max_dist > min_dist:
                # global_ref_dist is the distance at which the volume is visible in its entirety
                global_ref_dist = min_dist + 0.45 * (max_dist - min_dist)
                # a value between 0 and 1 that represents how close we are to the global view
                homing_progress = float(
                    np.clip((new_dist - min_dist) / max(global_ref_dist - min_dist, 1e-6), 0.0, 1.0)
                )
                """
                    when we are close to the global view we want to move the focal point 
                    faster towards the center of the volume
                    so we increase the weightbased on the homing progress (how close we are), but we clamp it 
                    so that we don't move too fast neither too slow
                """
                homing_weight = float(np.clip(step + 0.25 * homing_progress, 0.05, 0.65))
            else:
                homing_weight = float(np.clip(step * 1.5, 0.10, 0.50))

            # adjust the focal point
            new_focal = focal_point + homing_weight * (center - focal_point)
            if bounds is not None:
                new_focal = self.clamp_point_to_bounds(new_focal, bounds)

        # update the camera position based on the new focal point and distance
        # new focal + new distance multiplied by the versor
        new_pos = new_focal + view_dir_from_focal * new_dist

        # this clamp must stay: it is the only thing that keeps the wheel zoom inside the limits,
        # because _stop_wheel_event stops the wheel event before it gets to _limit_zoom
        new_pos = self.clamp_camera_position(new_pos, new_focal, min_dist, max_dist)

        return new_pos, new_focal

    def _get_cursor_target_3d(self) -> Vec3D:
        """
        this function projects the current 2D mouse cursor position onto the 3D plane orthogonal
        to the camera passing through the current focal point (we take is z), clamped to volume bounds.

        Parameters:
            None

        Returns:
            the 3D coordinates of the target point under the cursor, clamped,
            as a numpy array of shape (3,)
        """
        camera = self.plotter.camera
        focal = np.array(camera.GetFocalPoint(), dtype=np.float64)

        iren = self.plotter.iren.interactor
        if iren is None:
            return focal

        x, y = iren.GetEventPosition()
        renderer = self.plotter.renderer

        """
            here we get the depth of the focal point:

            focal is a 3D point in world space, we need to get its depth in display space, 
            so that we can unproject the cursor position.

            to do this, we use:
            SetWorldPoint to set the world coordinates of the focal point, the 4th is
            the homogeneous coordinate. 

            then we call WorldToDisplay to convert it to display coordinates 

            and at the end we call GetDisplayPoint to get the display coordinates of the focal point, 
            which is a 3D point in display space where the 3rd coordinate is the depth value.

            now we have the depth

            (Idea stolen from Mario xD)
            dictionary:

            Homogeneous coordinates: are a system of coordinates used in projective and computer 
            geometry that represent an n-dimensional point using n+1 numbers.
            they are used to do Unified Matrix Transformations, which allows to represent translations, 
            rotations, scaling, and perspective projections in a single matrix form.

            World space: is the coordinate system in which the 3D objects are defined, it is a global
            coordinate system that is independent of the camera or the viewer.

            Display space: is the coordinate system in which the 2D screen coordinates are defined,
            it is a local coordinate system that depends on the camera and the viewport.

            World Coordinates: are the coordinates of a point in world space, they are usually represented
            as (x, y, z) or (x, y, z, w)

            Display Coordinates: are the coordinates of a point in display space, they are usually represented
            as (x, y, z) where z is the depth value.
        """

        renderer.SetWorldPoint(focal[0], focal[1], focal[2], 1.0)
        renderer.WorldToDisplay()
        focal_depth = renderer.GetDisplayPoint()[2]

        # now we set the display point to the cursor position with the depth of the focal point,
        # and we call DisplayToWorld to get the world coordinates of the cursor position at that
        # depth, which is the point on the plane orthogonal to the camera passing through the focal point.
        renderer.SetDisplayPoint(float(x), float(y), float(focal_depth))
        renderer.DisplayToWorld()
        # 4d point in world coordinates
        world_pt = renderer.GetWorldPoint()

        if world_pt[3] == 0.0:
            return focal

        # to get the 3D coordinates of the target point,
        # we divide the first three coordinates by the 4th coordinate
        target_3d = np.array(world_pt[:3], dtype=np.float64) / world_pt[3]

        # clamp the target just in case it is outside bounds
        if self.volume_bounds is not None:
            target_3d = self.clamp_point_to_bounds(target_3d, self.volume_bounds)

        return target_3d

    def _apply_wheel_zoom(self, direction: int) -> None:
        """
        this function executes a single zoom step toward the cursor.

        Parameters:
            direction: 1 for zoom in, -1 for zoom out
        Returns:
            None
        """
        camera = self.plotter.camera
        position = np.array(camera.GetPosition(), dtype=np.float64)
        focal_point = np.array(camera.GetFocalPoint(), dtype=np.float64)

        target_3d = self._get_cursor_target_3d()

        vol_center = self.volume_center if self.volume_center is not None else focal_point

        new_pos, new_focal = self.compute_local_zoom_step(
            position=position,
            focal_point=focal_point,
            target_point=target_3d,
            volume_center=vol_center,
            direction=direction,
        )

        # avoid waste of rendering again as in the limit zoom
        if not (np.allclose(new_pos, position) and np.allclose(new_focal, focal_point)):
            camera.SetFocalPoint(*new_focal)
            camera.SetPosition(*new_pos)
            self.plotter.renderer.ResetCameraClippingRange()
            self._request_moving_render()

    def _request_render(self) -> None:
        """
        This function asks Qt to repaint the view, and the repaint draws it once.
        more requests before the repaint are merged into one, so we can call it after every change.

        we don't use self.plotter.render(): it draws the view right away, and then the repaint that
        pyvistaqt asks for draws it a second time.

        Returns:
            None
        """
        # the plotter has two update(): QWidget.update from Qt and BasePlotter.update from PyVista.
        # we want the Qt one, so we call it by name instead of relying on the order of the parent classes
        QWidget.update(self.plotter)

    def _request_moving_render(self) -> None:
        """
        This function asks for a redraw of the view at the lower quality used while the camera moves,
        and starts the timer that asks for a full quality redraw when the wheel stops.

        Returns:
            None
        """
        render_window = self.plotter.render_window
        if render_window is None or self.plotter.iren is None:
            return

        render_window.SetDesiredUpdateRate(self.plotter.iren.interactor.GetDesiredUpdateRate())
        self._request_render()
        self._full_quality_timer.start()

    def _request_full_quality_render(self) -> None:
        """
        This function asks for a redraw of the view at full quality.
        it is called by the timer when the wheel stops, and by clear.

        Returns:
            None
        """
        # the timer can fire after the plotter has been closed
        render_window = self.plotter.render_window
        if render_window is None or self.plotter.iren is None:
            return

        # if the user started dragging the view in the meantime, VTK draws it at full quality itself
        # when the drag ends (state 0 means no interaction)
        style = self.plotter.iren.interactor.GetInteractorStyle()
        if style is not None and style.GetState() != 0:
            return

        render_window.SetDesiredUpdateRate(self.plotter.iren.interactor.GetStillUpdateRate())
        self._request_render()

    def _set_volume_quality(self, _obj: object, _event: str) -> None:
        """
        This function is called by VTK before every redraw: while the view moves the volume is drawn
        at a lower resolution, when it is still at full resolution.
        the view moves when the render window asks for more frames per second than the still rate:
        VTK does it while the user drags the view, _request_moving_render does it for the wheel.

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """
        render_window = self.plotter.render_window
        if render_window is None or self.plotter.iren is None:
            return
        actor = self.plotter.actors.get("volume")
        if actor is None:
            return

        moving = render_window.GetDesiredUpdateRate() > self.plotter.iren.interactor.GetStillUpdateRate()
        actor.mapper.SetImageSampleDistance(MOVING_IMAGE_SAMPLE_DISTANCE if moving else 1.0)

    def _stop_wheel_event(self, tag: int) -> None:
        """
        This function stops the wheel event after our zoom, so it does not reach the default VTK zoom.
        with the wheel factor at 0 the default zoom does not move the camera, but it still draws
        the view two more times, once at full quality.

        Parameters:
            tag: the tag returned by AddObserver for our wheel observer

        Returns:
            None
        """
        self.plotter.iren.interactor.GetCommand(tag).SetAbortFlag(1)

    def _on_mouse_wheel_forward(self, _obj: object, _event: str) -> None:
        self._apply_wheel_zoom(direction=1)
        self._stop_wheel_event(self._wheel_forward_tag)

    def _on_mouse_wheel_backward(self, _obj: object, _event: str) -> None:
        self._apply_wheel_zoom(direction=-1)
        self._stop_wheel_event(self._wheel_backward_tag)

    """
        here i start the logic for the roi selection by click and drag
        for doing this i need to use the ray concept, it identifies the line that goes from
        the camera through the 3d space, so every point on this line.

        once we identify the ray we have to find the intersection with the volume
    """

    # i could refactor get_cursor_target_3d using this func, but i'll do it in the future
    # this is like the abstracted version of the code in get_cursor_target_3d
    def _display_to_world(self, x: float, y: float, depth: float) -> Vec3D | None:
        """
        This function converts a 2d point at a certain depth in display space to 3d world coordinates.

        Parameters:
            x: first coordinate in display space
            y: second coordinate in display space
            depth: the depth value in display space

        Returns:
            the 3D coordinates in world space as a numpy array of shape (3,)
            or None if the conversion is not possible
        """
        renderer = self.plotter.renderer
        # we set the display point to the given coordinates
        renderer.SetDisplayPoint(float(x), float(y), float(depth))
        # convert the coordinates
        renderer.DisplayToWorld()
        # get the world coordinates
        world_pt = renderer.GetWorldPoint()

        if world_pt[3] == 0.0:
            return None
        # we divide the first three coordinates by the fourth to get the 3D coordinates in world space
        # as i already mentioned we have a 4th coordinate because of GetWorldPoint,
        # which returns a 4D point in homogeneous coordinates
        return np.array(world_pt[:3], dtype=np.float64) / world_pt[3]

    def _get_cursor_ray_3d(self, screen_pos: tuple[int, int] | None = None) -> tuple[Vec3D, Vec3D] | None:
        """
        This function computes the 3D ray in the world space corresponding to the 2d cursor position

        Parameters:
            screen_pos: optional tuple of (x, y) coordinates in display space

        Returns:
            a tuple of two numpy arrays (ray_start, ray_end) representing the ray in 3D space
            this ray goes from Near plane(depth = 0.0) to Far plane(depth = 1.0)
        """

        if screen_pos is None:
            iren = self.plotter.iren.interactor
            if iren is None:
                return None
            x, y = iren.GetEventPosition()
        else:
            x, y = screen_pos

        ray_start = self._display_to_world(x, y, 0.0)
        ray_end = self._display_to_world(x, y, 1.0)
        if ray_start is None or ray_end is None:
            return None

        return ray_start, ray_end

    @staticmethod
    def _ray_intersects_bounds(ray_start: Vec3D, ray_end: Vec3D, bounds: Bounds6D) -> Vec3D | None:
        """
        this function calculates the first 3d point of intersection between a ray and the
        volume bounds aligned with the axes.
        it uses the slab method.

        SLAB METHOD: the idea is to consider the volume as the intersection of three slabs, one for each axis.
        a ray intersects the volume if and only if the time interval during which it travels inside all
        three slabs simultaneously is valid and overlapping

        Parameters:
            ray_start: the starting point of the ray in 3D space
            ray_end: the ending point of the ray in 3D space
            bounds: the bounds of the volume as a tuple (xmin, xmax, ymin, ymax, zmin, zmax)

        Returns:
            the first intersection point of the ray with the volume bounds as a numpy array of shape (3,)
            or None if there is no intersection
        """

        start = np.asarray(ray_start, dtype=np.float64)
        end = np.asarray(ray_end, dtype=np.float64)

        direction = end - start

        # box_min and box_max are the minimum and maximum coordinates of the volume bounds
        box_min = np.array([bounds[0], bounds[2], bounds[4]], dtype=np.float64)
        box_max = np.array([bounds[1], bounds[3], bounds[5]], dtype=np.float64)

        t_enter = 0.0
        t_exit = 1.0

        # now we iterate over the three axes (x, y, z) to compute the intersection intervals
        for i in range(3):
            # first case: ray parallel to the slab
            if abs(direction[i]) < 1e-12:
                # we check if the ray is outside the slab, if it is we return None, otherwise we continue
                if start[i] < box_min[i] or start[i] > box_max[i]:
                    return None

            # second case: ray not parallel to the slab
            else:
                # the ray is P(t) = start + t * direction,
                # in the i axes we have start[i] + t * direction[i]
                # i use inv_d just for efficiency
                inv_d = 1.0 / direction[i]
                # t value when it intersects box_min and box_max in the i axes, box[i] is our P(t)
                # we just resolve box_[i] = start[i] + t * direction[i] for t
                t1 = (box_min[i] - start[i]) * inv_d
                t2 = (box_max[i] - start[i]) * inv_d
                # we don't know which one is the near and which one is the far intersection
                # (dir could be negative), so we take the min and max
                t_near = min(t1, t2)
                t_far = max(t1, t2)

                # update t_enter and t_exit
                t_enter = max(t_enter, t_near)
                t_exit = min(t_exit, t_far)

                # if the enter time is greater than the exit time, the ray misses the box,
                # so we return None
                if t_enter > t_exit:
                    return None

        # we now return the first intersection point of the ray with the volume
        return start + t_enter * direction

    def pick_volume_bounds_point(
        self,
        screen_pos: tuple[int, int] | None = None,
        *,
        clamp_if_outside: bool = False,
    ) -> Vec3D | None:
        """
        find the 3D point on `self.volume_bounds` under the mouse cursor.


        Parameters:
            screen_pos: coordinates (x, y) in pixel optional (se None usa GetEventPosition()).
            clamp_if_outside:
                - False (used on the first click): returns None if the user clicks outside the volume.
                - True (used during the drag): if the cursor goes outside the volume's bounds,
                  it still projects the point and clamps it to the edges of `self.volume_bounds`.

        Returns:
            the 3D coordinates of the point on the volume bounds under the cursor, or None
            if the cursor is outside the volume and `clamp_if_outside` is False
        """
        if self.volume_bounds is None:
            return None

        ray = self._get_cursor_ray_3d(screen_pos)
        if ray is None:
            return None

        hit = self._ray_intersects_bounds(ray[0], ray[1], self.volume_bounds)
        if hit is not None:
            return hit

        if not clamp_if_outside:
            return None

        # Fallback during the drag outside the volume:
        # we use the point projected on the focal plane and already clamped to self.volume_bounds
        return self._get_cursor_target_3d()

    # ROI selection methods

    @property
    def roi_mode(self) -> RoiMode:
        """
        This property returns the current ROI selection mode.

        Returns:
            str: The current ROI selection mode, which can be one of the following:
                - RoiMode.INACTIVE: No ROI selection is active.
                - RoiMode.WAITING_FIRST_POINT: waiting the first click to start the ROI selection.
                - RoiMode.DRAGGING: the user is dragging the mouse to select the ROI.
                - RoiMode.EDITING: the user is editing the ROI after it has been created.
        """
        return self._roi_mode

    @property
    def current_roi(self) -> RegionOfInterest | None:
        """
        This property returns the current Region of Interest being selected or edited or None.

        Returns:
            RegionOfInterest | None: The current ROI object if one is being selected or edited,
            otherwise None.
        """
        return self._current_roi

    def start_roi_selection(self) -> None:
        """
        This method starts the ROI selection process.
        It sets the ROI mode to "waiting_first_point" and prepares the viewport for ROI selection.
        if there is no volume loaded, it does nothing.

        Returns:
            None
        """
        if self.volume_bounds is None:
            return

        self._disable_roi_box_widget()
        self._remove_roi_preview_actor()
        self._roi_start_point = None
        self._current_roi = None
        self._roi_mode = RoiMode.WAITING_FIRST_POINT
        self.setCursor(Qt.CursorShape.CrossCursor)
        self._request_render()
        self.roi_selection_started.emit()

    def cancel_roi_selection(self) -> None:
        """
        This method cancels the ROI selection process.
        It resets the ROI mode to "inactive" and removes any ROI preview from the viewport.

        Returns:
            None
        """
        self._roi_mode = RoiMode.INACTIVE
        self._roi_start_point = None
        self._current_roi = None
        self._disable_roi_box_widget()
        self._remove_roi_preview_actor()
        self.unsetCursor()
        self._full_quality_timer.stop()
        self._request_full_quality_render()
        self.roi_cancelled.emit()

    def _remove_roi_preview_actor(self) -> None:
        """
        removes the ROI preview actor from the plotter if it exists
        """
        if "roi_preview" in self.plotter.actors:
            self.plotter.remove_actor("roi_preview", render=False)
        self._roi_box_poly = None

    def _update_roi_preview_box(self, bounds: Bounds6D) -> None:
        """
        Creates or updates in-place the roi_preview that shows the ROI in 3D space.
        Parameters:
            bounds: The bounds of the ROI to visualize as a 3D box.

        Returns:
            None
        """
        # we create a box from the bounds and extract its edges to visualize it as a wireframe
        box_edges = pv.Box(bounds=bounds).extract_all_edges()

        # if the roi_preview already exists, we update it in-place to avoid creating a new actor
        if self._roi_box_poly is not None and "roi_preview" in self.plotter.actors:
            self._roi_box_poly.shallow_copy(box_edges)
            self._roi_box_poly.Modified()
            return

        # if the roi_preview does not exist, we create it and add it to the plotter
        self._roi_box_poly = pv.PolyData(box_edges)
        self.plotter.add_mesh(
            self._roi_box_poly,
            color="cyan",
            line_width=2.5,
            name="roi_preview",
            render=False,
        )

    def _get_camera_view_direction(self) -> Vec3D:
        """Returns the view direction of the camera (focal_point - position)"""
        camera = self.plotter.camera
        pos = np.array(camera.GetPosition(), dtype=np.float64)
        focal = np.array(camera.GetFocalPoint(), dtype=np.float64)
        return focal - pos

    def _on_left_button_press(self, _obj: object, _event: str) -> None:
        """
        when the user left-clicks, we check if we are in ROI selection mode and
        if we are waiting for the first point, if so, we block the camera rotation

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """
        if self._roi_mode != RoiMode.WAITING_FIRST_POINT:
            return

        # just for comodity, i use stop_wheel_event here and in the func below,
        # to abort the default vtk event, we could refactor the func and make it more generic
        # but it is not a big deal for now
        self._stop_wheel_event(self._left_press_tag)

        # we pick the 3D point on the volume bounds under the cursor, without clamping it
        # if the user clicks outside the volume, we don't start the ROI selection as i said
        # in the function pick_volume_bounds_point
        hit = self.pick_volume_bounds_point(clamp_if_outside=False)
        if hit is None:
            return

        self._roi_start_point = hit
        self._roi_mode = RoiMode.DRAGGING

    def _on_mouse_move(self, _obj: object, _event: str) -> None:
        """
        during mouse movement, if we are in ROI dragging mode, we calculate the second 3D point on the volume,
        construct the ROI with extended depth, and update the preview box on screen.

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """
        if self._roi_mode != RoiMode.DRAGGING or self._roi_start_point is None or self.volume_bounds is None:
            return

        self._stop_wheel_event(self._mouse_move_tag)

        # we pick the 3D point on the volume bounds under the cursor, clamping it if it's outside
        second_point = self.pick_volume_bounds_point(clamp_if_outside=True)
        if second_point is None:
            return

        # we construct the ROI with the two points and the current view direction
        view_dir = self._get_camera_view_direction()
        self._current_roi = RegionOfInterest.from_points(
            self._roi_start_point,
            second_point,
            volume_bounds=self.volume_bounds,
            view_direction=view_dir,
        )
        self._update_roi_preview_box(self._current_roi.bounds)
        self._request_moving_render()
        self.roi_updated.emit(self._current_roi)

    def _on_left_button_release(self, _obj: object, _event: str) -> None:
        """
        on left mouse button release, if we are in ROI dragging mode, we finalize the ROI selection.
        it passes to 'editing' mode, restores the cursor, and requests a full quality render of the viewport.

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """
        if self._roi_mode != RoiMode.DRAGGING:
            return

        self._stop_wheel_event(self._left_release_tag)

        # if the user did not move the mouse, we still create a valid initial ROI around the clicked point
        # we are covered by the min size of the ROI, so we don't need to worry about it being too small
        # the user could restart the selection it is his fault don't blame me for that
        if self._current_roi is None and self._roi_start_point is not None and self.volume_bounds is not None:
            view_dir = self._get_camera_view_direction()
            self._current_roi = RegionOfInterest.from_points(
                self._roi_start_point,
                self._roi_start_point,
                volume_bounds=self.volume_bounds,
                view_direction=view_dir,
            )
            self._update_roi_preview_box(self._current_roi.bounds)

        if self._current_roi is not None:
            self._enable_roi_box_widget(self._current_roi.bounds)
        self._roi_mode = RoiMode.EDITING
        self.unsetCursor()
        self._full_quality_timer.stop()
        self._request_full_quality_render()
        self.roi_updated.emit(self._current_roi)

    def _ensure_roi_box_widget(self) -> None:
        """
        Creates and configures the VTK box widget and its representation the first time
        they are needed. Rotation is disabled so the box always stays axis-aligned

        Parameters:
            None

        Returns:
            None
        """
        if self._roi_box_widget is not None and self._roi_box_rep is not None:
            return

        iren = self.plotter.iren.interactor
        if iren is None:
            return

        rep = vtkBoxRepresentation()
        # if i don't put 1.0, the default is 0.5 so every time it would be like half the size
        rep.SetPlaceFactor(1.0)
        # we want the box to be drawn from the inside, so the user can see the volume inside it
        # normally the box is drawn from the outside, so it occludes the volume inside it
        rep.InsideOutOn()

        rep.SetHandleSize(14.0)

        # TODO: we could make the color of handles and box choosable in the left panel
        # and maybe also some hover effect on the handles, but for now we keep it simple

        widget = vtkBoxWidget2()
        widget.SetInteractor(iren)
        widget.SetRepresentation(rep)

        # disable rotation so the user can only resize faces or translate the box along X, Y, Z
        widget.SetRotationEnabled(False)

        # while the user drags a handle, update and clamp the ROI at moving quality
        widget.AddObserver(vtkCommand.InteractionEvent, self._on_box_widget_interaction)
        # when the user releases the handle, draw the volume at full quality
        widget.AddObserver(vtkCommand.EndInteractionEvent, self._on_box_widget_end_interaction)

        self._roi_box_rep = rep
        self._roi_box_widget = widget

    def _enable_roi_box_widget(self, bounds: Bounds6D) -> None:
        """
        Places the VTK box widget on `bounds` and turns it on for interactive editing.

        Parameters:
            bounds: The bounds of the ROI to visualize as a 3D box.

        Returns:
            None
        """
        self._ensure_roi_box_widget()
        if self._roi_box_rep is None or self._roi_box_widget is None:
            return

        # PlaceWidget take the bounds and positions the handles
        self._roi_box_rep.PlaceWidget(list(bounds))
        self._roi_box_widget.On()

    def _disable_roi_box_widget(self) -> None:
        """
        Turns off the VTK box widget handles if they are active.

        Parameters:
            None
        Returns:
            None
        """
        if self._roi_box_widget is not None:
            self._roi_box_widget.Off()

    def _on_box_widget_interaction(self, _obj: object, _event: str) -> None:
        """
        Called by VTK whenever the user drags one of the 6 handles
        of the box widget. Reads the new bounds, clamps them to `self.volume_bounds`,
        and updates both the widget and the cyan preview box.

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """
        if self._roi_mode != RoiMode.EDITING or self._roi_box_rep is None or self.volume_bounds is None:
            return

        # get bound returns the position of the handles right now
        raw_bounds = self._roi_box_rep.GetBounds()
        # disable the shrinking behavior, we could add a toggle to decide if the user wants it or not
        if self._current_roi is not None:
            raw_bounds = self._slide_inside_volume(raw_bounds, self._current_roi, self.volume_bounds)
        self._current_roi = RegionOfInterest.from_bounds(
            raw_bounds,
            volume_bounds=self.volume_bounds,
        )

        # snap the widget handles back inside volume_bounds if the user dragged past the volume edge
        self._roi_box_rep.PlaceWidget(list(self._current_roi.bounds))
        self._update_roi_preview_box(self._current_roi.bounds)
        self._request_moving_render()
        self.roi_updated.emit(self._current_roi)

    def _on_box_widget_end_interaction(self, _obj: object, _event: str) -> None:
        """
        Called by VTK when the user finishes dragging a handle on the box widget.
        Requests a full-quality render of the volume.

        Parameters:
            _obj: the object that called the event
            _event: the event that was called

        Returns:
            None
        """
        if self._roi_mode != RoiMode.EDITING:
            return

        self._full_quality_timer.stop()
        self._request_full_quality_render()

    def accept_roi_selection(self) -> RegionOfInterest | None:
        """
        Confirms the currently edited ROI, turns off the 3D editing handles and preview box,
        resets the mode to INACTIVE, and emits `roi_accepted` with the final RegionOfInterest.

        Parameters:
            None

        Returns:
            RegionOfInterest | None: The confirmed ROI, or None if no ROI was in editing mode.
        """
        if self._roi_mode != RoiMode.EDITING or self._current_roi is None:
            return None

        # read the latest bounds from the box widget representation one last time
        if self._roi_box_rep is not None and self.volume_bounds is not None:
            self._current_roi = RegionOfInterest.from_bounds(
                self._roi_box_rep.GetBounds(),
                volume_bounds=self.volume_bounds,
            )

        accepted_roi = self._current_roi

        # clean up the interactive widget and preview wireframe
        self._roi_mode = RoiMode.INACTIVE
        self._roi_start_point = None
        self._disable_roi_box_widget()
        self._remove_roi_preview_actor()
        self.unsetCursor()
        self._full_quality_timer.stop()
        self._request_full_quality_render()

        self.roi_accepted.emit(accepted_roi)
        return accepted_roi

    def set_roi_preview(self, roi: RegionOfInterest) -> None:
        """
        Sets or updates the ROI preview and 3D box widget from external coordinates
        (for example when the user types coordinates in the UI text fields).

        Parameters:
            roi: The RegionOfInterest object containing the new bounds to visualize.

        Returns:
            None
        """
        if self.volume_bounds is None:
            return

        self._current_roi = RegionOfInterest.from_bounds(
            roi.bounds,
            volume_bounds=self.volume_bounds,
        )
        self._roi_mode = RoiMode.EDITING
        self.unsetCursor()
        self._update_roi_preview_box(self._current_roi.bounds)
        self._enable_roi_box_widget(self._current_roi.bounds)
        self._request_full_quality_render()
        self.roi_updated.emit(self._current_roi)

    @staticmethod
    def _slide_inside_volume(
        raw: Bounds6D,
        previous: RegionOfInterest,
        volume_bounds: Bounds6D,
        tol: float = 1e-6,
    ) -> Bounds6D:
        """
        If `raw` is the previous ROI only translated (same size on all axes), moves it back
        inside the volume without changing its size. Otherwise a face is being resized, so
        `raw` is returned as it is and the normal clamp applies.

        Parameters:
            raw: The new bounds of the ROI as a tuple (xmin, xmax, ymin, ymax, zmin, zmax).
            previous: The previous RegionOfInterest object before the change
            volume_bounds: The bounds of the volume as a tuple (xmin, xmax, ymin, ymax, zmin, zmax).
            tol: A small tolerance value to determine if the size of the ROI has changed on any axis.
        """
        prev = previous.bounds

        """
            we want to check if the size of the ROI on this axis has changed
            lo and hi are the indices of the lower and upper bounds 
            for this axis in the bounds tuple
            ex. min_x and max_x and so on for y and z
        """
        for axis in range(3):
            lo, hi = 2 * axis, 2 * axis + 1
            # if the size has changed, we return raw and let the normal clamp apply
            if abs((raw[hi] - raw[lo]) - (prev[hi] - prev[lo])) > tol:
                return raw

        # if the size is the same, we slide it back inside the volume bounds
        out: list[float] = []
        for axis in range(3):
            lo, hi = 2 * axis, 2 * axis + 1
            # we calculate the size of the ROI on this axis
            size = prev[hi] - prev[lo]
            """
            we clamp the lower bound:
            with min(raw .. bla bla) we ensure that the min cannot be greater
            than volume_max (it is like the border we cannot cross it) - size 
            because that would make the max go outside the volume bounds

            then we take the max between volume_min (same as above we want to make 
            sure that roi start before the border) and the previous result, 
            so that the min cannot be less than volume_min for the same reason as above

            i don't know if u will understand what i'm trying to say, it'd be easier to 
            explain with a drawing, if whoever is reviewing wants one i can send it on whatsapp
            """
            new_lo = max(volume_bounds[lo], min(raw[lo], volume_bounds[hi] - size))
            # the upper bound is just the lower bound plus the size, we don't need to clamp it
            out.extend((new_lo, new_lo + size))
        return (out[0], out[1], out[2], out[3], out[4], out[5])
