"""
PyVista demo: the same features as the napari demo, with PyVista (VTK) for the 3D view.

pyvistaqt's QtInteractor is a normal Qt widget, placed in our QMainWindow with the same
side panel as the napari demo. PyVista has no time axis: on every frame change the
volume values are replaced and the points and tracks of that frame are drawn again.

Redraws are asked with the Qt `update()` of the widget, not with `plotter.render()`: the
view is a QOpenGLWidget, so render() draws once and Qt draws again when it repaints.

Usage:
    uv run python -m demos.pyvista_demo
    uv run python -m demos.pyvista_demo file.czi [blobs.parquet tracks.parquet]
    uv run python -m demos.pyvista_demo --random 95 512 512
"""

import sys

import numpy as np
import pyvista as pv
from numpy.typing import NDArray
from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow
from pyvistaqt import QtInteractor

from demos.controls import ControlPanel
from demos.data import DemoData, from_args

POINT_SIZE_PX: float = 24.0
TAIL_FRAMES: int = 20  # same as the napari demo
TRACK_COLORS: int = 20  # the tab20 colormap
PICK_TOLERANCE_UM: float = 15.0


def to_xyz_um(zyx: NDArray[np.float64], voxel_um: tuple[float, float, float]) -> NDArray[np.float64]:
    """
    Convert (n, 3) z, y, x in voxels to (n, 3) x, y, z in micrometers, the order VTK uses.

    Args:
        zyx: Positions in voxels.
        voxel_um: (z, y, x) voxel size in micrometers.

    Returns:
        Positions in micrometers.
    """
    return zyx[:, ::-1] * np.array(voxel_um[::-1])


def tail_lines(tracks: NDArray[np.float64], t: int, voxel_um: tuple[float, float, float]) -> pv.PolyData:
    """
    The last TAIL_FRAMES positions of each track up to frame `t`, as polylines.

    Args:
        tracks: (n, 5) rows of track id, t, z, y, x, sorted by track id and then time.
        t: The current frame.
        voxel_um: (z, y, x) voxel size in micrometers.

    Returns:
        One polyline per track with at least two positions in the window.
    """
    rows = tracks[(tracks[:, 1] <= t) & (tracks[:, 1] > t - TAIL_FRAMES)]
    starts = np.flatnonzero(np.diff(rows[:, 0], prepend=-1))  # first row of each track
    lengths = np.diff(np.append(starts, len(rows)))
    # VTK line cells: number of points followed by their indices
    cells = [
        np.concatenate(([n], np.arange(s, s + n))) for s, n in zip(starts, lengths, strict=True) if n >= 2
    ]
    lines = np.concatenate(cells) if cells else np.empty(0, dtype=int)
    mesh = pv.PolyData(to_xyz_um(rows[:, 2:5], voxel_um), lines=lines)
    mesh.point_data["color"] = rows[:, 0] % TRACK_COLORS  # neighbouring ids get different colors
    return mesh


class PyVistaDemo(QMainWindow):
    """
    Window with the PyVista view in the central area and the control panel on the right.
    """

    def __init__(self, data: DemoData) -> None:
        super().__init__()
        self.setWindowTitle(f"PyVista demo - {data.name}")
        self.resize(1400, 900)
        self.data = data
        self.frame = 0
        self.show_points = len(data.points) > 0
        self.show_tracks = len(data.tracks) > 0
        self.show_roi = True
        # sorted by track id and time, so the rows of a track are next to each other
        self.tracks = data.tracks[np.lexsort((data.tracks[:, 1], data.tracks[:, 0]))]
        self.frame_points = np.empty((0, 3))
        self.frame_rows = np.empty(0, dtype=int)

        self.plotter = QtInteractor(self)
        self.setCentralWidget(self.plotter.interactor)
        self.plotter.set_background("black")

        first = data.read_frame(0)
        low, high = (int(v) for v in np.percentile(first, (1, 99.9)))
        nz, ny, nx = data.frame_shape
        grid = pv.ImageData(dimensions=(nx, ny, nz), spacing=data.voxel_um[::-1])
        grid.point_data["intensity"] = first.ravel()  # C order: x changes fastest, as VTK expects
        self.volume = self.plotter.add_volume(
            grid,
            scalars="intensity",
            cmap="gray",
            clim=(low, high),
            blending="maximum",
            show_scalar_bar=False,
            pickable=False,
        )
        # keep our own references: the plotter keeps only the Python object of the last mapper, and
        # when it is dropped the lookup table stored on it is lost (contrast and gamma stop working)
        self.volume_mapper = self.volume.mapper
        self.volume_prop = self.volume.prop
        self.volume_prop.interpolation_type = "linear"  # PyVista uses nearest: blocky with few z slices
        # add_volume works on its own copy of the grid: new frames are written into that one
        self.volume_grid = self.volume_mapper.dataset

        self.panel = ControlPanel(
            data.n_frames,
            data.frame_shape,
            int(first.max() * 1.5),
            (low, high),
            has_points=self.show_points,
            has_tracks=self.show_tracks,
        )
        dock = QDockWidget("Controls", self)
        dock.setWidget(self.panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.panel.frame_changed.connect(self._set_frame)
        self.panel.contrast_changed.connect(self._set_contrast)
        self.panel.gamma_changed.connect(self._set_gamma)
        self.panel.points_toggled.connect(self._show_points)
        self.panel.tracks_toggled.connect(self._show_tracks)
        self.panel.roi_toggled.connect(self._show_roi)
        self.panel.roi_changed.connect(self._set_roi)

        # a left click picks the nearest point of a pickable actor (only the points are pickable)
        self.plotter.enable_point_picking(
            callback=self._on_pick,
            show_message=False,
            show_point=False,
            left_clicking=True,
            pickable_window=False,
        )
        self.statusBar().showMessage("Click a point to see its data")

        self._draw_overlays()
        self._set_roi(*self.panel.roi_bounds())
        self.plotter.reset_camera()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 (Qt method name)
        self.plotter.close()  # VTK needs to release its window before Qt destroys it
        super().closeEvent(event)

    def _set_frame(self, t: int) -> None:
        self.frame = t
        self.volume_grid.point_data["intensity"][:] = self.data.read_frame(t).ravel()
        self.volume_grid.Modified()
        self._draw_overlays()
        self.plotter.update()

    def _set_contrast(self, low: int, high: int) -> None:
        self.volume_mapper.lookup_table.scalar_range = (low, high)
        self.volume_prop.reapply_lookup_table()
        self.plotter.update()

    def _set_gamma(self, gamma: float) -> None:
        # VTK has no gamma for volumes: the gray ramp of the lookup table is bent instead
        ramp = np.linspace(0.0, 1.0, 256) ** gamma
        self.volume_mapper.lookup_table.values = (np.column_stack([ramp] * 4) * 255).astype(np.uint8)
        self.volume_prop.reapply_lookup_table()
        self.plotter.update()

    def _show_points(self, visible: bool) -> None:
        self.show_points = visible
        self._draw_overlays()
        self.plotter.update()

    def _show_tracks(self, visible: bool) -> None:
        self.show_tracks = visible
        self._draw_overlays()
        self.plotter.update()

    def _show_roi(self, visible: bool) -> None:
        self.show_roi = visible
        self._set_roi(*self.panel.roi_bounds())

    def _set_roi(self, z0: int, z1: int, y0: int, y1: int, x0: int, x1: int) -> None:
        self.plotter.remove_actor("roi", render=False)
        if self.show_roi:
            sz, sy, sx = self.data.voxel_um
            box = pv.Box(bounds=(x0 * sx, x1 * sx, y0 * sy, y1 * sy, z0 * sz, z1 * sz))
            self.plotter.add_mesh(
                box, style="wireframe", color="cyan", name="roi", pickable=False, render=False
            )
        self.plotter.update()

    def _draw_overlays(self) -> None:
        # PyVista has no time axis: the actors of the current frame replace the old ones (same name)
        self.plotter.remove_actor(["points", "tracks"], render=False)
        self.frame_rows = np.flatnonzero(self.data.points[:, 0] == self.frame)
        self.frame_points = to_xyz_um(self.data.points[self.frame_rows, 1:4], self.data.voxel_um)
        if self.show_points and len(self.frame_rows):
            self.plotter.add_points(
                self.frame_points,
                name="points",
                color="yellow",
                point_size=POINT_SIZE_PX,
                render_points_as_spheres=True,
                render=False,
            )
        if self.show_tracks:
            lines = tail_lines(self.tracks, self.frame, self.data.voxel_um)
            if lines.n_lines:
                self.plotter.add_mesh(
                    lines,
                    scalars="color",
                    cmap="tab20",
                    clim=(0, TRACK_COLORS - 1),
                    line_width=2,
                    show_scalar_bar=False,
                    name="tracks",
                    pickable=False,
                    render=False,
                )

    def _on_pick(self, position: NDArray[np.float64]) -> None:
        if not len(self.frame_points):
            return
        distances = np.linalg.norm(self.frame_points - position, axis=1)
        nearest = int(distances.argmin())
        if distances[nearest] > PICK_TOLERANCE_UM:
            return
        row = self.data.point_info.iloc[self.frame_rows[nearest]]
        self.statusBar().showMessage(", ".join(f"{name} {value:g}" for name, value in row.items()))


def main() -> int:
    """
    Start the demo with the data chosen on the command line (see `demos.data.from_args`).
    """
    data = from_args(sys.argv[1:])
    app = QApplication.instance() or QApplication(sys.argv)
    window = PyVistaDemo(data)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
