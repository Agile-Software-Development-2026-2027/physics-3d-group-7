import numpy as np
import pyvista as pv

# Generic rank-3 tensor, indexed as (z, y, x)
type Image[T: np.number | np.bool_] = np.ndarray[tuple[int, int, int], np.dtype[T]]


def view_image(volume: Image[np.number]) -> None:
    """Render a 3D Numpy array in a graphical window on the fly.

    Useful to inspect a volume during development and unit testing.
    Not used in production.

    Args:
        volume: the 3D Numpy array to render.
    """

    volume = volume.astype(np.float32) if volume.dtype == np.bool_ else volume

    grid = pv.ImageData()
    grid.dimensions = volume.shape
    grid.point_data["values"] = volume.ravel(order="F")

    plotter = pv.Plotter()
    plotter.add_volume(grid, scalars="values", cmap="viridis", opacity="sigmoid", show_scalar_bar=True)

    plotter.add_axes()  # type: ignore
    plotter.show_bounds(grid=True, xlabel="X", ylabel="Y", zlabel="Z")  # type: ignore

    plotter.show()
