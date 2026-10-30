# Choosing the 3D view library: napari or PyVista

This is the GUI part of the research story SCRUM-22 (subtask SCRUM-30). The question is which library should draw the 3D view of the new application: napari, which the legacy code already uses, or PyVista, which the PO suggested.

**Decision**: on 26 October the group chose **PyVista** (see [Decision](#decision)).

## Context

The PO's main complaint about the current tool is that it is not fluid. Running the legacy code on the sample files (SCRUM-25) showed where the slowness comes from:

- every time the frame changes, the legacy GUI runs preprocessing and blob detection again in a background thread, with a 300 ms delay. The view shows the new volume while the blob count still belongs to an older frame;
- the only freeze longer than one second was in the matplotlib histograms, not in napari.

So part of the problem is how the legacy GUI is built, not the library. In the new application detection and linking run once and the GUI only shows their results. With that design, the question is which library shows volumes, points and tracks better.

Requirements for the view: a native desktop window (not a web page), Python 3.14, Qt6 (our GUI base is a PySide6 window, #4), volume rendering of time series of 3D stacks, points and tracks on top, and good speed on real volumes of about 95 x 512 x 512 voxels.

## Options discarded

- **Toga (BeeWare)**: native widgets of each system, but no widget to embed an OpenGL/3D view, so it cannot host napari, PyVista or any volume renderer.
- **trame (Kitware)**: the interface is a web page, shown in a browser or in a web view window. We want a native window. It would make sense only if remote access to the lab machine were needed.
- **PyVista without Qt**: the plain VTK window only has controls drawn inside the 3D view, too little for an application with many parameters and panels.
- **wxPython + VTK**: possible, but a smaller ecosystem, napari would not be available, and our GUI base is already Qt.
- **Dear PyGui**: fast for 2D interfaces and plots, but it has no volume rendering, which we would have to write from scratch.
- **vispy directly**: it is the engine under napari. Using it directly means writing ourselves what napari already gives (layers, time axis, points, tracks, picking).
- **fastplotlib**: fast (WGPU), but a younger project whose volume rendering is recent, and with fewer users to rely on.

## How the two candidates were compared

We wrote two demos with exactly the same features, the same side panel (frame slider with play, contrast, gamma, points, tracks, ROI box) and the same data, inside our own Qt window:

- napari demo: draft #7 (SCRUM-26)
- PyVista demo: draft #8 (SCRUM-27)

The data are the two sample files with the blobs and tracks of the legacy code, and random data of two sizes, the larger one with the size of a real volume (95 x 512 x 512 voxels, 50 MB per frame).

How each library fits in our Qt window is described in `gui_qt_integration.md` (#9, SCRUM-28). In short: both can be placed in our window as a normal Qt widget (napari through `QtViewer`, PyVista through pyvistaqt's `QtInteractor`). napari handles the time axis, points of the current frame, track tails and gamma by itself. With PyVista we write those parts: the demo is 172 lines of code against 143 for napari.

## Measures

`demos/bench.py` (draft #10, SCRUM-29) runs the same steps on both demos, each run in a new process: start the program, change frame from the panel, rotate the view with a simulated mouse drag, read the memory. Every step waits until the view is drawn and the GPU has finished, and the script checks that the drag really moved the camera. Medians of 5 runs, alternating the libraries, on a laptop plugged in to mains power, with a Ryzen 7 7730U, an integrated AMD Radeon GPU, 16 GB of RAM and a 60 Hz screen.

| data (one frame) | library | startup | frame change | mouse rotation | RAM |
|---|---|---|---|---|---|
| Crop-02 (11x100x100) | napari | 5.9 s | 56 ms | 62 fps | 545 MB |
| | PyVista | 3.3 s | 25 ms | 47 fps | 469 MB |
| Crop-01 (21x150x150) | napari | 5.7 s | 61 ms | 61 fps | 608 MB |
| | PyVista | 3.3 s | 26 ms | 47 fps | 496 MB |
| random (40x256x256) | napari | 5.3 s | 41 ms | 49 fps | 750 MB |
| | PyVista | 3.3 s | 32 ms | 42 fps | 460 MB |
| random, real size (95x512x512) | napari | 7.0 s | 87 ms | 24 fps | 2441 MB |
| | PyVista | 6.5 s | 100 ms | 20 fps | 573 MB |

What the numbers say:

- **Startup**: PyVista starts 2 to 2.5 s earlier on the sample files (importing napari takes about 3 s, PyVista 1.3 s). At real size the two are close (6.5 and 7.0 s), because PyVista needs 3.3 s to load the first volume.
- **Frame change**: on the sample files PyVista is about twice as fast (25 against 56-61 ms). At real size the two are close: 87 ms for napari, 100 ms for PyVista, and single runs overlap (PyVista from 76 to 106 ms, napari from 79 to 88 ms). Both keep up with a play at 10 frames per second.
- **Rotation**: napari reaches the limit of the screen (60 fps) on the sample files, PyVista 47 fps. At real size the two are close: 24 and 20 fps. With the mouse, PyVista draws about 2.3 times for every mouse move (VTK draws, then Qt repaints the widget), napari once.
- **Memory**: napari keeps the frames it has read in a cache (a quarter of the RAM by default, configurable), so at real size it grows to 2.4 GB after 22 frames, and a frame seen before comes back at once. Without the cache it opens the real-size data with 770 MB, PyVista with 570 MB.

The real-size runs were slower in the last repeats for both libraries (rotation from 33 to 24 fps for napari, from 27 to 20 fps for PyVista), probably because the laptop heats up. The medians are close to the slower values.

## Corrections made during the measures

Two problems were found and fixed, and every number above was measured after the fixes:

- **Power**: the first series of runs was made on battery. Windows slows the laptop down to save energy, and the times were up to twice as long and not stable (napari frame change on Crop-02: 120-140 ms on battery, 52-59 ms plugged in). The benchmark now records whether the laptop is plugged in, and all 40 runs above were.
- **napari drag**: in the first version of the napari demo the points layer was in "select" mode, so a mouse drag drew a selection box instead of rotating the view, and the benchmark measured that. The demo now keeps the normal mode and picks points with a click, and the benchmark checks that the camera moved.

Our first conclusion, based on those runs, was that napari was twice as fast and three times more fluid at real size. That was wrong: measured correctly the two libraries are close.

## Is it the library or our PyVista code?

We know napari better than PyVista, so we checked whether the PyVista demo slows it down, on the real-size volume:

- One fix was already applied before the measures: with pyvistaqt, `plotter.render()` drew every change about twice; asking redraws with Qt `update()` brought the frame change on Crop-02 down by about 40%.
- A PyVista frame change at real size splits into reading the frame (10 ms), copying it into VTK (5 ms), points and tracks (4 ms) and drawing (64 ms), which is mostly uploading the new volume to the GPU.
- The other VTK volume mappers are slower: `gpu` and `open_gl` take 135-175 ms per frame change and rotate at 6-10 fps. The default `smart` mapper used in the measures is the fastest.
- The double draw per mouse move comes from the way pyvistaqt puts VTK in a `QOpenGLWidget`, chosen to work with Wayland. When VTK draws by itself, once per step and without Qt, it rotates the real-size volume at 50 fps, twice what napari reaches with Qt and the mouse. So PyVista's engine is not the limit, the Qt integration is. Embedding VTK in Qt in a different way could make PyVista faster, but we have not tried it.

napari was not tuned at all either.

## What decides it

Speed does not decide between the two: on real volumes they are close, and each one is faster in some cases. The choice depends on what the group values more.

| | napari | PyVista |
|---|---|---|
| speed on real volumes | about the same (87 ms, 24 fps) | about the same (100 ms, 20 fps) |
| speed on small files | slower frame change, faster rotation | faster frame change, slower rotation |
| startup | 2 to 2.5 s slower on small files | faster |
| memory | grows with the cache (configurable) | lower |
| code to write | less: time series, tracks, layers built in | more: time handling, track tails, picking by hand |
| room to get faster | not tuned yet | VTK alone is fast, the Qt integration is the limit |
| who knows it | the legacy code and the researchers use it | suggested by the PO |

Before the group discussion our proposal was **napari, used as a widget (`QtViewer`) inside our own Qt window**, for the work it saves rather than for speed: time series, points of the current frame, tracks and the layer model are ready, so we can spend the time on the analysis features, and the researchers already know it. Its downsides are manageable:

- **Startup**: show our window first and create the napari view right after, and import napari only when it is needed (the CLI never imports it).
- **Memory**: set the size of napari's cache from our settings, depending on the machine.
- **`QtViewer` as a widget** is less documented than napari's own window: keep it behind one class of ours, pin the napari version and check it when updating.

PyVista is the better choice if startup time, memory and the PO's preference weigh more than the extra code, or if we are ready to work on the Qt integration to get the speed VTK can give.

## Decision

The group chose **PyVista** on 26 October. On real volumes the two libraries are about equally fast, so the choice came from the other points:

- **control**: with PyVista we write the time handling, the tracks and the picking ourselves, so we decide how every part of the view works and we can change it, instead of adapting to napari's layer model;
- **a simpler structure to follow**: our window talks to VTK directly, without a second application model in between;
- **less memory**, and a faster startup;
- **room to optimize**: VTK alone rotates the real-size volume at 50 fps, so the view can get faster by improving the Qt integration.

The price is more code of our own. The PyVista demo (#8) already shows how to write it.

What this means for the 3D view:

- it uses PyVista through pyvistaqt's `QtInteractor`, as a widget in our Qt window, like the demo;
- the pitfalls in `gui_qt_integration.md` apply: ask redraws with `update()` and not `render()`, keep a reference to the volume mapper and property, use linear interpolation, close the plotter when the window closes.

## Limits and next steps

- The numbers are for one laptop with an integrated GPU, plugged in. Absolute values will be different on the lab workstation, and the difference between the two libraries on real volumes is within the variation between runs.
- The real-size volume is random data with the right size and type. A real large file has not been tested yet: reading 50 MB per frame with czifile from disk will add to the frame change time of both libraries.
- Next steps: test a large real file, and try embedding VTK in Qt without pyvistaqt's double draw, to get closer to the 50 fps VTK reaches alone.
