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
