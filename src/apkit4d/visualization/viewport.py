import time

import numpy as np
import pyvista as pv
from PySide6.QtWidgets import QVBoxLayout, QWidget
from pyvistaqt import QtInteractor

"""
    in this file we define the viewport class, that is the widget that will be placed 
    at the center of the main window to visualize the 3D data.

    it is a subclass of Qwidget and it contains the QtInteractor that is used to interact with the 3D data.

"""


class Viewport(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Set up the vertical layout for the widget
        self.main_layout = QVBoxLayout(self)

        # Set the margins to 0 so that we use the entire space
        self.main_layout.setContentsMargins(0, 0, 0, 0)

        # that's the interactor we were talking about and here we add it to the layout
        self.plotter = QtInteractor(self)
        self.main_layout.addWidget(self.plotter.interactor)

        # set up of some viewport things
        self.plotter.set_background("gray")
        self.plotter.add_axes()

        self.min_zoom_dist = 0.0
        self.max_zoom_dist = float("inf")

        # we store the center and bounds
        self.volume_center: np.ndarray | None = None
        self.volume_bounds: tuple[float, float, float, float, float, float] | None = None

        # they are used in the zoom acceleration function
        self.last_zoom_time = 0.0
        self.current_zoom_factor = 0.01

        iren = self.plotter.iren.interactor  # vtkRenderWindowInteractor

        # disable the default zoom so i can implement mine
        style = iren.GetInteractorStyle()
        if style is not None:
            style.SetMouseWheelMotionFactor(0.0)

        for event in ("MouseWheelForwardEvent", "MouseWheelBackwardEvent"):
            iren.AddObserver(event, self._update_zoom_acceleration, 10.0)

        # observers for the zoom events with a lower priority than acceleration, so that
        # the acceleration is updated first
        iren.AddObserver("MouseWheelForwardEvent", self._on_mouse_wheel_forward, 5.0)
        iren.AddObserver("MouseWheelBackwardEvent", self._on_mouse_wheel_backward, 5.0)

        for event in (
            "InteractionEvent",
            "MouseWheelForwardEvent",
            "MouseWheelBackwardEvent",
            "EndInteractionEvent",
        ):
            iren.AddObserver(event, self._limit_zoom, -1.0)

        # TODO: decide how we are going to handle colors and other stuff like axes, grid, coordinates, etc.

        # TODO: the next step is also deactivating the default panning and maybe implement a custom one

    def show_volume(self, grid: pv.ImageData, reset_camera: bool = True):
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

        # here we add the volume, that is the blob data
        self.plotter.add_volume(grid, cmap="magma", opacity="linear", name="volume")

        # with this we can see the cube borders
        self.plotter.add_mesh(grid.outline(), color="white", line_width=2, name="outline")

        # store the center and bounds
        self.volume_center = np.array(grid.center, dtype=float)
        self.volume_bounds = grid.bounds

        # i think setting max and min zoom only the first time we show the volume or when we reset
        # should work, that kinda depends on how we are going to handle future ROIs
        if self.max_zoom_dist == float("inf") or reset_camera:
            diagonal = grid.length
            self.min_zoom_dist = diagonal * 0.1
            self.max_zoom_dist = diagonal * 4.0

        # since we work with 4D data i've put the reset as an option, we don't want to reset on every frame,
        # but it could be useful in some cases, so we leave it as an option for now.
        if reset_camera:
            self.plotter.reset_camera()

        # TODO: here we will need to handle the color map and the opacity
        # but for now we will use default values to try

    def show_blobs(self, poly: pv.PolyData):
        """
        This function is used to visualize the real blobs after the blob detection

        Parameters:
            poly (pv.PolyData): PyVista PolyData object that we mapped in the data_mapper.py file.
            it contains the data of specific blobs that we want to visualize.

        Returns:
            None
        """
        if poly is None or poly.n_points == 0:
            return

        # here we add the dectected blobs in the plotter
        self.plotter.add_mesh(poly, color="red", point_size=10.0, render_points_as_spheres=True, name="blobs")

    def clear(self):
        """
        This function is used to clear the viewport.

        it removes all the things from the plotter and resets the camera.

        Returns:
            None
        """
        self.volume_center = None
        self.volume_bounds = None
        self.min_zoom_dist = 0.0
        self.max_zoom_dist = float("inf")
        self.plotter.clear()
        self.plotter.reset_camera()

    def clamp_point_to_bounds(self, point, bounds):
        """
        This function is used to clamp a point to the 3d bounds of the volume, to ensure that
        the focal point of the zoom is always inside

        Parameters:
            point: the point to be clamped
            bounds: the bounds of the volume

        Returns:
            the clamped point
        """
        point = np.asarray(point, dtype=float)

        # if the bounds are not set, we return the point as it is,
        # since we don't have any bounds to clamp
        if bounds is None or len(bounds) != 6:
            return point

        mins = np.array([bounds[0], bounds[2], bounds[4]], dtype=float)
        maxs = np.array([bounds[1], bounds[3], bounds[5]], dtype=float)
        return np.clip(point, mins, maxs)

    def clamp_camera_position(self, position, focal_point, min_dist, max_dist):
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
        position = np.asarray(position, dtype=float)
        focal_point = np.asarray(focal_point, dtype=float)

        vec = position - focal_point
        dist = np.linalg.norm(vec)

        if dist == 0:
            return position

        # clip the distance to be within the min and max distance
        new_dist = np.clip(dist, min_dist, max_dist)
        return focal_point + (vec / dist) * new_dist

    def _limit_zoom(self, obj, event):
        """
        This function is used to limit the zoom of the camera.

        it is called when the user zooms in or out and checks distance between
        camera position and focal point, it calls the clamp function and updates
        the camera position if needed.

        Parameters:
            obj: the object that called the event
            event: the event that was called

        Returns:
            None
        """

        camera = self.plotter.camera
        position = np.array(camera.GetPosition())
        focal_point = np.array(camera.GetFocalPoint())

        new_pos = self.clamp_camera_position(position, focal_point, self.min_zoom_dist, self.max_zoom_dist)

        # avoid waste of rendering if the position is the same
        if not np.allclose(new_pos, position):
            camera.SetPosition(*new_pos)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()

    def _update_zoom_acceleration(self, obj, event):
        """
        This function is used to update the zoom acceleration of the camera.
        it is called when the user zooms in or out and checks the time between
        the last zoom event and the current zoom event, and updates the zoom factor

        Parameters:
            obj: the object that called the event
            event: the event that was called
        Returns:
            None
        """

        now = time.perf_counter()
        dt = now - self.last_zoom_time
        self.last_zoom_time = now

        # if the user is scrolling quickly, we increase the zoom factor
        if dt < 0.12:
            # increase the zoom factor by 50% but clamp it to a maximum of 0.35
            self.current_zoom_factor = min(self.current_zoom_factor * 1.5, 0.35)
        else:
            # factor reset
            self.current_zoom_factor = 0.01

        style = self.plotter.iren.interactor.GetInteractorStyle()
        if style is not None:
            style.SetMouseWheelMotionFactor(0.0)

    def compute_local_zoom_step(
        self,
        position,
        focal_point,
        target_point,
        volume_center,
        direction: int,
        zoom_factor: float,
        min_dist,
        max_dist: float,
        bounds=None,
    ) -> tuple[np.ndarray, np.ndarray]:
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

        pos = np.asarray(position, dtype=float)
        focal = np.asarray(focal_point, dtype=float)
        target = np.asarray(target_point, dtype=float)
        # if the volume center is not provided, we use the focal point as the center
        center = np.asarray(volume_center, dtype=float) if volume_center is not None else focal.copy()

        vec = pos - focal
        dist = float(np.linalg.norm(vec))
        if dist == 0.0:
            return pos, focal

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
            new_focal = focal + effective_alpha * (target - focal)
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
                homing_progress = np.clip(
                    (new_dist - min_dist) / max(global_ref_dist - min_dist, 1e-6), 0.0, 1.0
                )
                """
                    when we are close to the global view we want to move the focal point 
                    faster towards the center of the volume
                    so we increase the weightbased on the homing progress (how close we are), but we clamp it 
                    so that we don't move too fast neither too slow
                """
                homing_weight = float(np.clip(step + 0.25 * homing_progress, 0.10, 0.65))
            else:
                homing_weight = float(np.clip(step * 1.5, 0.10, 0.50))

            # adjust the focal point
            new_focal = focal + homing_weight * (center - focal)
            if bounds is not None:
                new_focal = self.clamp_point_to_bounds(new_focal, bounds)

        # update the camera position based on the new focal point and distance
        # new focal + new distance multiplied by the versor
        new_pos = new_focal + view_dir_from_focal * new_dist

        # clamping just to be sure, i think it could be deleted
        # but since i'm not sure i'll leave it for now
        new_pos = self.clamp_camera_position(new_pos, new_focal, min_dist, max_dist)

        return new_pos, new_focal

    def _get_cursor_target_3d(self) -> np.ndarray:
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
        focal = np.array(camera.GetFocalPoint(), dtype=float)

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
        target_3d = np.array(world_pt[:3], dtype=float) / world_pt[3]

        # clamp the target just in case it is outside bounds
        if self.volume_bounds is not None:
            target_3d = self.clamp_point_to_bounds(target_3d, self.volume_bounds)

        return target_3d

    def _apply_wheel_zoom(self, direction: int):
        """
        this function executes a single zoom step toward the cursor.

        Parameters:
            direction: 1 for zoom in, -1 for zoom out
        Returns:
            None
        """
        camera = self.plotter.camera
        position = np.array(camera.GetPosition(), dtype=float)
        focal_point = np.array(camera.GetFocalPoint(), dtype=float)

        target_3d = self._get_cursor_target_3d()

        vol_center = self.volume_center if self.volume_center is not None else focal_point

        new_pos, new_focal = self.compute_local_zoom_step(
            position=position,
            focal_point=focal_point,
            target_point=target_3d,
            volume_center=vol_center,
            direction=direction,
            zoom_factor=self.current_zoom_factor,
            min_dist=self.min_zoom_dist,
            max_dist=self.max_zoom_dist,
            bounds=self.volume_bounds,
        )

        # avoid waste of rendering again as in the limit zoom
        if not (np.allclose(new_pos, position) and np.allclose(new_focal, focal_point)):
            camera.SetFocalPoint(*new_focal)
            camera.SetPosition(*new_pos)
            self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()

    def _on_mouse_wheel_forward(self, obj, event):
        self._apply_wheel_zoom(direction=1)

    def _on_mouse_wheel_backward(self, obj, event):
        self._apply_wheel_zoom(direction=-1)
