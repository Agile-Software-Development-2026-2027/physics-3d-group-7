# Putting the 3D view in our Qt window: napari vs PyVista

This note answers how napari and PyVista fit inside our Qt application (SCRUM-28). The GUI base (#4) is a PySide6 `QMainWindow`, so the question is how each library puts its 3D view inside it and what that means for the rest of the code.

The group chose PyVista for the 3D view (see `gui_library_choice.md`, SCRUM-30). The napari parts stay here as a reference.

Everything below was tried in the two demos, which have the same features, the same side panel and the same data:

- napari demo: draft PR #7 (`demos/napari_demo.py`)
- PyVista demo: draft PR #8 (`demos/pyvista_demo.py`)

Versions: Python 3.14, PySide6 6.12, napari 0.9.2, PyVista 0.49.1, pyvistaqt 0.13.1, on Windows.

## napari

napari can be used in two ways.

**napari is the window.** This is the usual way: `napari.Viewer()` opens napari's own window, with its menus, layer list, layer controls and plugins. Our panels are added as dock widgets with `viewer.window.add_dock_widget(widget, area="right")`. The application lives inside napari.

**napari is a widget.** This is what the demo does. `QtViewer` is a normal Qt widget (a `QSplitter`) that we put in our own window:

```python
from napari.components import ViewerModel
from napari.qt import QtViewer

viewer = ViewerModel()
qt_viewer = QtViewer(viewer)
window.setCentralWidget(qt_viewer)

viewer.add_image(frames, scale=(1.0, *voxel_um), rendering="mip")  # frames is (t, z, y, x)
viewer.dims.ndisplay = 3
```

We keep control of the window, the menus and the layout. We lose napari's own menus and plugin system, and the layer list and layer controls are not shown. `QtViewer` still exposes them (`qt_viewer.layers`, `qt_viewer.controls`), so they can be put in our docks if we want them. It also brings its own time slider with a play button; the demo hides it (`qt_viewer.dims.hide()`) to use our panel.

## PyVista

`pyvistaqt.QtInteractor` is a `QOpenGLWidget`, so it goes in the window like any other widget. Our application is always the container:

```python
from pyvistaqt import QtInteractor

plotter = QtInteractor(window)
window.setCentralWidget(plotter.interactor)

actor = plotter.add_volume(grid, cmap="gray", blending="maximum")  # grid is a pv.ImageData of one frame
```

The window has to call `plotter.close()` when it is closed, so VTK releases its OpenGL window before Qt destroys it.

## Connecting our controls to the view

In both demos the controls are plain Qt widgets that emit signals, and each demo connects them to its view. The panel (`demos/controls.py`) is the same file for both, only the connected functions change.

napari works by properties: setting `layer.contrast_limits`, `layer.gamma` or `viewer.dims.set_current_step(0, t)` redraws the view by itself. It also has its own events, for example `viewer.dims.events.current_step`, to know when the view changes frame on its own (arrow keys). Most controls take one to three lines.

PyVista works by commands: we change the VTK objects and then ask a redraw with the widget's Qt `update()`. It has no time axis, so on every frame change we write the new volume values and draw again the points and the tracks of that frame. Track tails and gamma (VTK has no gamma for volumes, we bend the gray ramp of the lookup table) are written by hand. The demo is 172 lines of code against 143 for napari, without comments and docstrings.

## Long computations

Rendering has to run in the Qt main thread. Reading frames, preprocessing and detection must not, or the window freezes. The legacy GUI has this problem: it runs detection again on every frame change.

This does not depend on the viewer. `superqt.utils.thread_worker` (napari's `thread_worker` is built on the same idea) runs a function in a worker thread and sends the result back through a Qt signal in the main thread, where the view is updated. It works the same with napari and with PyVista. napari also reads lazy arrays (dask) one frame at a time, so a long file does not have to be in memory.

## Things to know

napari:

- clicks go to the active layer, which is the last one added unless we choose it;
- in "select" mode a Points layer turns every mouse drag into a box selection, so the view cannot be rotated: keep the normal mode and pick points with a click callback (`layer.get_value(..., view_direction=..., dims_displayed=..., world=True)` finds the point under the mouse in 3D);
- a Tracks layer with no data raises an error, so the layer is created only when there are tracks;
- line widths are in data units and the voxel scale stretches them (voxels are about 6 times taller than wide), so boxes and lines should be given in micrometers with scale 1;
- `viewer.camera` is deprecated since 0.9, use `viewer.scene.camera`.

PyVista:

- ask redraws with the widget's Qt `update()`: the view is a `QOpenGLWidget`, so `plotter.render()` draws once and Qt draws again when it repaints (every change drawn twice). The same double draw happens inside pyvistaqt when the user rotates with the mouse, and we cannot avoid it from our code;
- `add_volume` works on its own copy of the grid, new frames go into `actor.mapper.dataset`;
- keep our own reference to the volume mapper and property: the plotter keeps only the Python object of the last mapper, and the lookup table stored on it is lost when other actors are added (contrast and gamma stop working);
- the default volume interpolation is nearest, which looks blocky with few z slices, so we set it to linear;
- points and lines inside a bright part of the volume are partly hidden by it, while napari draws them on top.

## QML or widgets

Both views are `QWidget` subclasses. QML (Qt Quick) cannot host widgets, so a QML interface would mean rewriting the 3D views as Qt Quick items. The GUI is built in code with Qt Widgets, as agreed in the group.

## Qt binding

Both libraries reach Qt through `qtpy`, which picks PySide6, and both run with PySide6 6.12 on Python 3.14. PySide6 is LGPL, PyQt6 is GPL. On Linux machines without a screen (our CI) Qt needs the system library `libEGL`, installed in `ci.yml`.

## Starting the app without a console on Windows

A command in `[project.scripts]` always opens a console window on Windows. If the app is started with a double click, a `[project.gui-scripts]` entry (for example `apkit4d-gui`) starts it without the console. It needs a small `main()` without arguments next to `run(path)`. To decide together with the CLI (SCRUM-32).

## Summary

| | napari | PyVista |
|---|---|---|
| how it goes in our window | `QtViewer` widget, or napari is the window | `QtInteractor` widget |
| who owns the window | us (widget) or napari | us |
| time series | built in (4D data) | done by us on every frame |
| points, tracks, gamma | built in | points yes, track tails and gamma by hand |
| updating the view | set a property | change VTK objects and render |
| demo size | 143 lines | 172 lines |
| pitfalls | select mode blocks rotation, active layer, empty tracks, line widths and voxel scale | double draw with render(), copied grid, lost lookup table, nearest interpolation |

Speed and memory are measured in SCRUM-29, and the choice is in the final report (SCRUM-30).
