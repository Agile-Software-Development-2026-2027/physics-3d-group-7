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
from napari.qt import QtViewer
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDockWidget, QMainWindow

from demos.controls import ControlPanel
from demos.data import DemoData, load


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
        self.viewer.dims.axis_labels = ("t", "z", "y", "x")
        self.viewer.dims.ndisplay = 3
        self.viewer.dims.set_current_step(0, 0)  # napari starts from the middle frame otherwise
        self.qt_viewer.dims.hide()  # the frame slider is in our panel, as in the PyVista demo

        self.panel = ControlPanel(data.n_frames, int(first.max() * 1.5), (low, high))
        dock = QDockWidget("Controls", self)
        dock.setWidget(self.panel)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, dock)

        self.panel.frame_changed.connect(self._set_frame)
        self.panel.contrast_changed.connect(self._set_contrast)
        self.panel.gamma_changed.connect(self._set_gamma)
        # napari can also change frame by itself (arrow keys): keep the slider in sync
        self.viewer.dims.events.current_step.connect(self._on_step)

    def _set_frame(self, t: int) -> None:
        self.viewer.dims.set_current_step(0, t)

    def _set_contrast(self, low: int, high: int) -> None:
        self.image.contrast_limits = (low, high)

    def _set_gamma(self, gamma: float) -> None:
        self.image.gamma = gamma

    def _on_step(self, event: object) -> None:
        self.panel.show_frame(self.viewer.dims.current_step[0])


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
