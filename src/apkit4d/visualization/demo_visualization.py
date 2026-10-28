"""
this file is just a horrible demo to test the viewport you can use this to see how it works
it helps me to understand what is going on and what is missing

for example i noticed that the zoom is like a bit weird and not that smooth, but i will work
on that later, for now it works and i'm happy with it.
"""

import sys

import numpy as np
from PySide6.QtWidgets import QApplication

from apkit4d.visualization.data_mapper import create_volume_grid
from apkit4d.visualization.viewport import Viewport

SHAPE = (40, 64, 64)
VOXEL_SIZE = (2.0, 0.5, 0.5)
SIGMA = 3.0
CENTERS = [(12, 20, 20), (20, 32, 32), (28, 45, 40), (15, 45, 15), (25, 18, 48)]


def make_volume() -> np.ndarray:
    """Array (z, y, x) con una gaussiana 3D per ogni centro."""
    z, y, x = np.indices(SHAPE, dtype=np.float32)
    data = np.zeros(SHAPE, dtype=np.float32)
    for cz, cy, cx in CENTERS:
        r2 = (z - cz) ** 2 + (y - cy) ** 2 + (x - cx) ** 2
        data += np.exp(-r2 / (2 * SIGMA**2))
    return data


def main():
    app = QApplication(sys.argv)

    viewport = Viewport()
    viewport.resize(900, 700)
    viewport.setWindowTitle("Test Viewport 3D")

    grid = create_volume_grid(make_volume(), VOXEL_SIZE)
    viewport.show_volume(grid, reset_camera=True)

    viewport.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
