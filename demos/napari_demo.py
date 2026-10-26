"""
napari demo: 3D view of random data or of a .czi file, inside our own Qt window.

napari is used as a widget (QtViewer) placed in a QMainWindow, the way the real
application would host it, instead of letting napari open its own window. The side
panel is the same as in the PyVista demo.

Usage:
    uv run python -m demos.napari_demo
    uv run python -m demos.napari_demo file.czi [blobs.parquet tracks.parquet]
"""

import sys
from pathlib import Path

import dask
import dask.array as da
import numpy as np
from napari.components import ViewerModel
from napari.layers import Points, Tracks
from napari.qt import QtViewer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow

from demos.controls import ControlPanel
from demos.data import DemoData, load

POINT_SIZE_UM: float = 12.0  # about the size of an alga
TAIL_FRAMES: int = 20  # how much of the past path of each track is drawn
ROI_LINE_WIDTH: float = 1.0


def box_edges(z0: int, z1: int, y0: int, y1: int, x0: int, x1: int) -> np.ndarray:
    """
    The 12 edges of a box as napari vectors: one (start, direction) pair per edge.

    Args:
        z0, z1, y0, y1, x0, x1: Limits of the box in voxels.

    Returns:
        (12, 2, 3) array of edge start points and edge directions.
    """
    corners = np.array([(z, y, x) for z in (z0, z1) for y in (y0, y1) for x in (x0, x1)], dtype=float)
    # corner i has bits (z, y, x): two corners share an edge when they differ in exactly one bit
    edges = [(a, b) for a in range(8) for b in range(a + 1, 8) if (a ^ b).bit_count() == 1]
    return np.array([(corners[a], corners[b] - corners[a]) for a, b in edges])


def as_lazy_array(data: DemoData) -> da.Array:
    """
    Stack the frames as a (t, z, y, x) dask array: a frame is read only when napari shows it.

    Args:
        data: The demo data.

    Returns:
        The lazy 4D array.
    """
    frames = [
        da.from_delayed(dask.delayed(data.read_frame)(t), shape=data.frame_shape, dtype=np.uint16)
        for t in range(data.n_frames)
    ]
    return da.stack(frames)


class NapariDemo(QMainWindow):
    """
    Window with the napari view in the central area and the control panel on the right.
    """

    def __init__(self, data: DemoData) -> None:
        super().__init__()
        self.setWindowTitle(f"napari demo - {data.name}")
        self.resize(1400, 900)

        self.viewer = ViewerModel()
        self.qt_viewer = QtViewer(self.viewer)
        self.setCentralWidget(self.qt_viewer)

        # contrast from the first frame, so napari does not read every frame to compute it
        first = data.read_frame(0)
        low, high = (int(v) for v in np.percentile(first, (1, 99.9)))
        self.image = self.viewer.add_image(
            as_lazy_array(data),
            name="volume",
            scale=(1.0, *data.voxel_um),  # the time axis has no physical size
            contrast_limits=(low, high),
            colormap="gray",
            rendering="mip",
        )
        # the layers are created only when there is data: napari tracks fail on an empty table
        self.tracks: Tracks | None = None
        if len(data.tracks):
            self.tracks = self.viewer.add_tracks(
                data.tracks, name="tracks", scale=(1.0, *data.voxel_um), tail_length=TAIL_FRAMES
            )
        self.points: Points | None = None
        if len(data.points):
            # points in (t, z, y, x): napari shows only the ones of the current frame
            self.points = self.viewer.add_points(
                data.points,
                name="points",
                scale=(1.0, *data.voxel_um),
                features=data.point_info,
                size=POINT_SIZE_UM,
                face_color="transparent",
                border_color="yellow",
            )
            self.points.mode = "select"  # a click on a point selects it
            self.points.selected_data.events.items_changed.connect(self._on_point_selected)
        self.point_info = data.point_info

        self.viewer.dims.axis_labels = ("t", "z", "y", "x")
        self.viewer.dims.ndisplay = 3
        self.viewer.dims.set_current_step(0, 0)  # napari starts from the middle frame otherwise
        self.qt_viewer.dims.hide()  # the frame slider is in our panel, as in the PyVista demo

        self.panel = ControlPanel(
            data.n_frames,
            data.frame_shape,
            int(first.max() * 1.5),
            (low, high),
            has_points=self.points is not None,
            has_tracks=self.tracks is not None,
        )
        # the box is a 3D layer, so napari shows it in every frame of the 4D data. Its coordinates
        # are in micrometers with scale 1: with the voxel scale the lines would be 6 times wider in z
        self.voxel_um = np.array(data.voxel_um)
        self.roi = self.viewer.add_vectors(
            box_edges(*self.panel.roi_bounds()) * self.voxel_um,
            name="roi",
            edge_color="cyan",
            edge_width=ROI_LINE_WIDTH,
            vector_style="line",
        )
        if self.points is not None:
            # napari sends clicks to the active layer, the last one added unless we choose it
            self.viewer.layers.selection.active = self.points

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
        # napari can also change frame by itself (arrow keys): keep the slider in sync
        self.viewer.dims.events.current_step.connect(self._on_step)
        self.statusBar().showMessage("Click a point to see its data")

    def _set_frame(self, t: int) -> None:
        self.viewer.dims.set_current_step(0, t)

    def _set_contrast(self, low: int, high: int) -> None:
        self.image.contrast_limits = (low, high)

    def _set_gamma(self, gamma: float) -> None:
        self.image.gamma = gamma

    def _show_points(self, visible: bool) -> None:
        if self.points is not None:
            self.points.visible = visible

    def _show_tracks(self, visible: bool) -> None:
        if self.tracks is not None:
            self.tracks.visible = visible

    def _show_roi(self, visible: bool) -> None:
        self.roi.visible = visible

    def _set_roi(self, z0: int, z1: int, y0: int, y1: int, x0: int, x1: int) -> None:
        self.roi.data = box_edges(z0, z1, y0, y1, x0, x1) * self.voxel_um

    def _on_step(self, event: object) -> None:
        self.panel.show_frame(self.viewer.dims.current_step[0])

    def _on_point_selected(self, event: object) -> None:
        selected = list(self.points.selected_data) if self.points is not None else []
        if not selected:
            return
        row = self.point_info.iloc[selected[0]]
        self.statusBar().showMessage(", ".join(f"{name} {value:g}" for name, value in row.items()))


def main() -> int:
    """
    Start the demo with random data, or with the files given on the command line.
    """
    files = [Path(arg) for arg in sys.argv[1:]]
    data = load(*files)
    app = QApplication.instance() or QApplication(sys.argv)
    window = NapariDemo(data)
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
