"""
Benchmark of the GUI demos (SCRUM-29): startup, frame change, rotation and memory.

One run measures one library on one dataset in a fresh process and prints one JSON line.
The steps are the same for napari and PyVista: open the window, change frame through the
control panel, rotate the camera, read the memory. Every step waits until the view is drawn
and the GPU has finished, and counts the draws to check that the step really redrew.

`all` repeats every library and dataset in separate processes and writes one CSV row per
run; `summary` prints the medians of a CSV.

Usage:
    uv run python -m demos.bench napari --random 95 512 512 --frames 30
    uv run python -m demos.bench pyvista path/to/file.czi
    uv run python -m demos.bench all results.csv ../apkit4d-data
    uv run python -m demos.bench summary results.csv
"""

import csv
import json
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import psutil
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMainWindow, QWidget

from demos.data import DemoData, from_args

LIBRARIES: tuple[str, ...] = ("napari", "pyvista")
FRAME_CHANGES: int = 20
WARMUP_CHANGES: int = 2  # the first changes pay one-off costs (shaders, caches) and are not counted
ROTATION_STEPS: int = 60
DRAG_PX: int = 4  # mouse movement per rotation step
REPEATS: int = 5
MAX_EVENT_ROUNDS: int = 10
RESULT_PREFIX: str = "BENCH "


@dataclass
class View:
    """
    What the benchmark needs from a demo window; only this part differs between libraries.

    Attributes:
        window: The demo window.
        canvas: The Qt widget of the 3D view, where the mouse drag is sent.
        draws: Returns how many times the 3D view has been drawn so far.
        finish: Waits until the GPU has finished drawing.
        camera: Returns the camera state, to check that a drag really rotated the view (a redraw
            alone is not enough: in napari a drag can also draw a selection box).
    """

    window: QMainWindow
    canvas: QWidget
    draws: Callable[[], int]
    finish: Callable[[], None]
    camera: Callable[[], tuple[float, ...]]


def napari_view(data: DemoData) -> View:
    from demos.napari_demo import NapariDemo

    window = NapariDemo(data)
    canvas = window.qt_viewer.canvas._scene_canvas  # the vispy canvas that draws the scene
    count = [0]
    canvas.events.draw.connect(lambda event: count.__setitem__(0, count[0] + 1))
    camera = window.viewer.scene.camera
    return View(window, canvas.native, lambda: count[0], canvas.context.finish, lambda: tuple(camera.angles))


def pyvista_view(data: DemoData) -> View:
    from demos.pyvista_demo import PyVistaDemo

    window = PyVistaDemo(data)
    plotter = window.plotter
    count = [0]
    plotter.ren_win.AddObserver("EndEvent", lambda *args: count.__setitem__(0, count[0] + 1))
    return View(
        window,
        plotter.interactor,
        lambda: count[0],
        plotter.ren_win.WaitForCompletion,
        lambda: tuple(plotter.camera.position),
    )


def mouse(kind: QEvent.Type, widget: QWidget, position: QPoint, pressed: bool) -> QMouseEvent:
    """
    A left button mouse event at `position` inside `widget`.
    """
    button = Qt.MouseButton.NoButton if kind == QEvent.Type.MouseMove else Qt.MouseButton.LeftButton
    buttons = Qt.MouseButton.LeftButton if pressed else Qt.MouseButton.NoButton
    return QMouseEvent(
        kind,
        QPointF(position),
        QPointF(widget.mapToGlobal(position)),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )


def settle(app: QApplication, view: View, draws_before: int) -> bool:
    """
    Run the Qt events until the view has been drawn again, then wait for the GPU.

    Returns:
        Whether the view was drawn.
    """
    for _ in range(MAX_EVENT_ROUNDS):
        app.processEvents()
        if view.draws() > draws_before:
            break
    view.finish()
    return view.draws() > draws_before


def timed_step(app: QApplication, view: View, action: Callable[[], None]) -> tuple[float, bool]:
    """
    Time an action until its result is on screen.

    Returns:
        Seconds taken and whether the view was drawn.
    """
    draws_before = view.draws()
    start = time.perf_counter()
    action()
    drawn = settle(app, view, draws_before)
    return time.perf_counter() - start, drawn


def memory_mb() -> tuple[float, float]:
    """
    Current and peak memory of this process in MB (the peak is available on Windows only).
    """
    info = psutil.Process().memory_info()
    return info.rss / 2**20, getattr(info, "peak_wset", info.rss) / 2**20


def plugged_in() -> bool | None:
    """
    Whether the computer runs on mains power (None without a battery). On battery a laptop can
    slow down to save energy, so the runs must be done plugged in.
    """
    battery = psutil.sensors_battery()
    return None if battery is None else battery.power_plugged


def run(library: str, data_args: list[str]) -> dict[str, object]:
    """
    Measure one library on one dataset.

    Args:
        library: "napari" or "pyvista".
        data_args: Command line arguments for `demos.data.from_args`.

    Returns:
        The measures of this run.
    """
    app = QApplication.instance() or QApplication(sys.argv)

    start = time.perf_counter()
    import_module = {"napari": "demos.napari_demo", "pyvista": "demos.pyvista_demo"}[library]
    __import__(import_module)  # the library import is part of the startup
    import_s = time.perf_counter() - start

    start = time.perf_counter()
    data = from_args(data_args)
    data_s = time.perf_counter() - start

    start = time.perf_counter()
    view = {"napari": napari_view, "pyvista": pyvista_view}[library](data)
    view.window.show()
    settle(app, view, 0)
    window_s = time.perf_counter() - start
    process_s = time.time() - psutil.Process().create_time()
    ram_open_mb, _ = memory_mb()

    # frames spread over the file, so they are not read from a cache
    frames = np.linspace(0, data.n_frames - 1, WARMUP_CHANGES + FRAME_CHANGES + 1).astype(int)[1:]
    slider = view.window.panel.frame  # type: ignore[attr-defined]  # both demos have the same panel
    frame_s, frames_drawn = [], 0
    for i, t in enumerate(frames):
        seconds, drawn = timed_step(app, view, lambda t=t: slider.setValue(int(t)))
        frames_drawn += drawn
        if i >= WARMUP_CHANGES:
            frame_s.append(seconds)

    read_s = []
    for t in frames[WARMUP_CHANGES:]:
        start = time.perf_counter()
        data.read_frame(int(t))
        read_s.append(time.perf_counter() - start)

    # rotation as the user does it: a left button drag on the view, one small move per step
    canvas = view.canvas
    center = canvas.rect().center()
    camera_before = view.camera()
    QApplication.sendEvent(canvas, mouse(QEvent.Type.MouseButtonPress, canvas, center, pressed=True))
    rotation_drawn = 0
    start = time.perf_counter()
    for step in range(1, ROTATION_STEPS + 1):
        position = center + QPoint(DRAG_PX * step, 0)
        move = mouse(QEvent.Type.MouseMove, canvas, position, pressed=True)
        _, drawn = timed_step(app, view, lambda move=move: QApplication.sendEvent(canvas, move))
        rotation_drawn += drawn
    rotation_s = time.perf_counter() - start
    QApplication.sendEvent(canvas, mouse(QEvent.Type.MouseButtonRelease, canvas, position, pressed=False))
    rotated = view.camera() != camera_before

    ram_end_mb, ram_peak_mb = memory_mb()
    view.window.close()
    return {
        "library": library,
        "data": data.name,
        "frame_shape": "x".join(map(str, data.frame_shape)),
        "process_s": process_s,
        "import_s": import_s,
        "data_s": data_s,
        "window_s": window_s,
        "frame_ms_median": 1000 * statistics.median(frame_s),
        "frame_ms_max": 1000 * max(frame_s),
        "read_ms_median": 1000 * statistics.median(read_s),
        "rotation_fps": ROTATION_STEPS / rotation_s,
        "ram_open_mb": ram_open_mb,
        "ram_end_mb": ram_end_mb,
        "ram_peak_mb": ram_peak_mb,
        "frames_drawn": f"{frames_drawn}/{len(frames)}",
        "rotations_drawn": f"{rotation_drawn}/{ROTATION_STEPS}",
        "rotated": rotated,
        "plugged_in": plugged_in(),
    }


def datasets(data_dir: Path) -> dict[str, list[str]]:
    """
    The datasets of the comparison: the two sample files and random data of two sizes.
    """
    crops = {
        name: [
            str(data_dir / f"Experiment-933-{crop}.czi"),
            str(data_dir / "out" / f"Experiment-933-{crop}_blobs.parquet"),
            str(data_dir / "out" / f"Experiment-933-{crop}_tracks.parquet"),
        ]
        for name, crop in (("crop02", "Crop-02"), ("crop01", "Crop-01"))
    }
    return crops | {
        "random_256": ["--random", "40", "256", "256", "--frames", "60"],
        "random_512": ["--random", "95", "512", "512", "--frames", "30"],
    }


def run_all(out_csv: Path, data_dir: Path) -> None:
    """
    Run every library on every dataset REPEATS times, each run in a new process.
    """
    if plugged_in() is False:
        print("warning: the computer is on battery, the times will be slower and less stable", flush=True)
    rows = []
    for name, args in datasets(data_dir).items():
        for repeat in range(REPEATS):
            for library in LIBRARIES:  # alternate the libraries, so a slower moment hits both
                done = subprocess.run(
                    [sys.executable, "-m", "demos.bench", library, *args],
                    capture_output=True,
                    text=True,
                    timeout=900,
                )
                line = next((x for x in done.stdout.splitlines() if x.startswith(RESULT_PREFIX)), None)
                if line is None:
                    print(f"{name} {library} {repeat}: failed\n{done.stderr[-2000:]}", flush=True)
                    continue
                row = {"dataset": name, "repeat": repeat} | json.loads(line[len(RESULT_PREFIX) :])
                rows.append(row)
                print(
                    f"{name} {library} {repeat}: start {row['process_s']:.1f} s, "
                    f"frame {row['frame_ms_median']:.0f} ms, {row['rotation_fps']:.0f} fps"
                    + ("" if row["rotated"] else " (the drag did not rotate: rotation not valid)"),
                    flush=True,
                )
    with out_csv.open("w", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    summary(out_csv)


def summary(csv_path: Path) -> None:
    """
    Print the median of every measure for each dataset and library.

    The rotation uses only the runs where the drag really rotated the camera.
    """
    with csv_path.open(newline="") as file:
        rows = list(csv.DictReader(file))
    measures = ("process_s", "window_s", "frame_ms_median", "read_ms_median", "rotation_fps", "ram_end_mb")
    print(f"{'dataset':12} {'library':8} " + " ".join(f"{m:>15}" for m in measures) + "  rotated runs")
    for name in dict.fromkeys(row["dataset"] for row in rows):
        for library in LIBRARIES:
            runs = [row for row in rows if row["dataset"] == name and row["library"] == library]
            if not runs:
                continue
            rotated = [row for row in runs if row.get("rotated") == "True"]
            medians = [
                statistics.median(float(row[m]) for row in (rotated if m == "rotation_fps" else runs))
                if (rotated or m != "rotation_fps")
                else float("nan")
                for m in measures
            ]
            print(
                f"{name:12} {library:8} "
                + " ".join(f"{v:15.1f}" for v in medians)
                + f"  {len(rotated)}/{len(runs)}"
            )


def main() -> None:
    """
    Dispatch the command line: a single run, `all` or `summary`.
    """
    command, *rest = sys.argv[1:]
    if command == "all":
        run_all(Path(rest[0]), Path(rest[1]))
    elif command == "summary":
        summary(Path(rest[0]))
    else:
        print(RESULT_PREFIX + json.dumps(run(command, rest)), flush=True)


if __name__ == "__main__":
    main()
