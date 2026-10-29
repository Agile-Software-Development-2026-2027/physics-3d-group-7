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

        iren = self.plotter.iren.interactor  # vtkRenderWindowInteractor

        for event in (
            "InteractionEvent",
            "MouseWheelForwardEvent",
            "MouseWheelBackwardEvent",
            "EndInteractionEvent",
        ):
            iren.AddObserver(event, self._limit_zoom, -1.0)

        # TODO: decide how we are going to handle colors and other stuff like axes, grid, coordinates, etc.

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
        self.plotter.clear()
        self.plotter.reset_camera()

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
