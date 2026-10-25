"""
napari demo: 3D view of random data or of a .czi file, inside our own Qt window.

napari is used as a widget (QtViewer) placed in a QMainWindow, the way the real
application would host it, instead of letting napari open its own window.

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
from PySide6.QtWidgets import QApplication, QMainWindow

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
    Window with the napari view in the central area.
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
        self.image = self.viewer.add_image(
            as_lazy_array(data),
            name="volume",
            scale=(1.0, *data.voxel_um),  # the time axis has no physical size
            contrast_limits=tuple(np.percentile(first, (1, 99.9))),
            colormap="gray",
            rendering="mip",
        )
        self.viewer.dims.axis_labels = ("t", "z", "y", "x")
        self.viewer.dims.ndisplay = 3
        self.viewer.dims.set_current_step(0, 0)  # napari starts from the middle frame otherwise


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
