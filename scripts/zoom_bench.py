"""
Time the 3D volume view when zooming in, with the settings we can change.

Run it from the repo folder, no window opens and it takes a few minutes:
    uv run python scripts/zoom_bench.py
    uv run --with czifile python scripts/zoom_bench.py --czi Experiment-933-Crop-01.czi

For each volume and setting it prints the milliseconds of:
    still   one frame at full quality, what is drawn when the view stops
    moving  one frame while the mouse drags the view
    wheel   one mouse wheel step, which draws a moving frame and then a still one
at zoom x1 (whole volume in view), x2, x4 and x8.
"""

import argparse
import platform
import statistics
import time
from pathlib import Path

import numpy as np
import pyvista as pv
import vtk

ZOOMS = (1, 2, 4, 8)
VOXEL_UM = (18.1, 2.8, 2.8)  # z, y, x of the sample files
# desired update rates of the VTK interactor: while moving and when still
MOVING_RATE = 15.0
STILL_RATE = 0.0001
WARMUP = 2  # frames before timing, so the adaptive mapper settles


def tiny_volume():
    """The 10x10x10 test from the group chat: two bright voxels, voxel size 1."""
    img = np.zeros((10, 10, 10), dtype=np.float32)
    img[1, 2, 3] = 0.3
    img[9, 8, 6] = 0.234
    return "tiny", img, (1.0, 1.0, 1.0)


def real_size_volume(seed=0):
    """Noise plus 40 gaussian spots, the size of a full acquisition."""
    rng = np.random.default_rng(seed)
    shape = (95, 512, 512)
    img = (150 + 20 * rng.standard_normal(shape, dtype=np.float32)).clip(0)
    z, y, x = np.ogrid[-4:5, -8:9, -8:9]
    spot = 2000 * np.exp(-0.5 * ((z / 1.2) ** 2 + (y / 2.5) ** 2 + (x / 2.5) ** 2))
    for cz, cy, cx in rng.integers((4, 8, 8), (shape[0] - 4, shape[1] - 8, shape[2] - 8), size=(40, 3)):
        img[cz - 4 : cz + 5, cy - 8 : cy + 9, cx - 8 : cx + 9] += spot
    return "real size", img.astype(np.uint16), VOXEL_UM


def czi_volume(path):
    """Frame 0 of a .czi file with axes T, Z, Y, X."""
    import czifile  # ty: ignore[unresolved-import]  # optional, only for --czi

    scene = czifile.CziFile(path).scenes[0]
    if scene.dims != ("T", "Z", "Y", "X"):
        raise ValueError(f"expected axes T, Z, Y, X, got {scene.dims}")
    scales = scene.coord_scales  # meters
    voxel = (scales["Z"] * 1e6, scales["Y"] * 1e6, scales["X"] * 1e6)
    return path.stem, scene(T=0).asarray(), voxel


def to_grid(img, voxel):
    """The same grid as create_volume_grid in visualization/data_mapper.py."""
    grid = pv.ImageData(dimensions=img.shape[::-1], spacing=voxel[::-1])
    grid.point_data["values"] = img.ravel()
    return grid


def add_now(plotter, grid):
    """What Viewport.show_volume does today: PyVista defaults, the quality is never lowered."""
    return plotter.add_volume(grid, cmap="magma", opacity="linear", name="volume")


def add_adaptive(plotter, grid):
    """Same, but VTK lowers the quality while the view moves (on in plain VTK, off in PyVista)."""
    actor = add_now(plotter, grid)
    actor.mapper.InteractiveAdjustSampleDistancesOn()
    return actor


def add_half_res(plotter, grid):
    """
    One ray every 2x2 pixels, also when still.

    The smart mapper does not expose this, so it uses the GPU mapper directly, with the
    sample distance taken from the voxel spacing as the smart mapper does (same times at full res).
    """
    actor = plotter.add_volume(grid, cmap="magma", opacity="linear", name="volume", mapper="gpu")
    actor.mapper.LockSampleDistanceToInputSpacingOn()
    actor.mapper.SetImageSampleDistance(2.0)
    return actor


SETTINGS = {"now": add_now, "adaptive": add_adaptive, "half res": add_half_res}


def median_ms(win, step, rate, n):
    """Median time of n calls of `step`, each waiting for the GPU to finish."""
    win.SetDesiredUpdateRate(rate)
    times = []
    for i in range(WARMUP + n):
        start = time.perf_counter()
        step(i)
        win.WaitForCompletion()
        if i >= WARMUP:
            times.append(time.perf_counter() - start)
    return 1000 * statistics.median(times)


def time_setting(add, grid, size, n):
    """Still, moving and wheel times at each zoom for one setting."""
    pl = pv.Plotter(off_screen=True, window_size=size)
    add(pl, grid)
    pl.add_mesh(grid.outline(), color="white", line_width=2, name="outline")
    win, cam = pl.ren_win, pl.camera
    assert win is not None

    # a VTK interactor without a window, to send it mouse wheel events
    iren = vtk.vtkGenericRenderWindowInteractor()
    iren.SetRenderWindow(win)
    iren.SetInteractorStyle(vtk.vtkInteractorStyleTrackballCamera())
    iren.Initialize()
    iren.SetEventInformation(size[0] // 2, size[1] // 2)

    def turn(i):
        cam.Azimuth(1)
        win.Render()

    def wheel(i):
        # forward and back, so the zoom stays the same
        if i % 2 == 0:
            iren.MouseWheelForwardEvent()
        else:
            iren.MouseWheelBackwardEvent()

    pl.reset_camera()  # ty: ignore[missing-argument]
    times = {"still": [], "moving": [], "wheel": []}
    for zoom in ZOOMS:
        if zoom > 1:
            cam.Dolly(2)
            pl.renderer.ResetCameraClippingRange()
        times["still"].append(median_ms(win, turn, STILL_RATE, n))
        times["moving"].append(median_ms(win, turn, MOVING_RATE, n))
        times["wheel"].append(median_ms(win, wheel, STILL_RATE, n))
    pl.close()
    return times


def gpu_name():
    """The OpenGL renderer VTK uses, to check it is the real GPU."""
    pl = pv.Plotter(off_screen=True, window_size=[64, 64])
    win = pl.ren_win
    assert win is not None
    win.Render()
    report = win.ReportCapabilities()
    pl.close()
    for line in report.splitlines():
        if "renderer string" in line:
            return line.split(":", 1)[1].strip()
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Time the 3D volume view when zooming in.")
    parser.add_argument(
        "--czi", nargs="*", type=Path, default=[], help="also time frame 0 of these .czi files"
    )
    parser.add_argument(
        "--size", nargs=2, type=int, default=(1280, 800), metavar=("W", "H"), help="window size"
    )
    parser.add_argument("--frames", type=int, default=5, help="timed frames per measure")
    args = parser.parse_args()
    size = tuple(args.size)

    system = f"{platform.system()} {platform.release()}"
    versions = f"pyvista {pv.__version__}, vtk {vtk.vtkVersion.GetVTKVersion()}"
    print(f"GPU: {gpu_name()} | {system} | {versions}")
    print(f"window {size[0]}x{size[1]}, milliseconds, median of {args.frames}")

    volumes = [tiny_volume, real_size_volume] + [lambda p=p: czi_volume(p) for p in args.czi]
    zooms = "".join(f"{'x' + str(z):>6}" for z in ZOOMS)
    for make in volumes:
        name, img, voxel = make()
        grid = to_grid(img, voxel)
        print(f"\n{name} {'x'.join(map(str, img.shape))}")
        print(f"{'':10}{'still':^24} | {'moving':^24} | {'wheel step':^24}")
        print(f"{'zoom':10}{zooms} | {zooms} | {zooms}")
        for label, add in SETTINGS.items():
            t = time_setting(add, grid, size, args.frames)
            cells = ["".join(f"{v:6.0f}" for v in t[kind]) for kind in ("still", "moving", "wheel")]
            print(f"{label:10}{' | '.join(cells)}", flush=True)


if __name__ == "__main__":
    main()
