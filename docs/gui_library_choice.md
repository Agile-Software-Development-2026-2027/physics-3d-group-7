# Choosing the 3D view library: napari or PyVista

This is the GUI part of the research story SCRUM-22 (subtask SCRUM-30). The question is which library should draw the 3D view of the new application: napari, which the legacy code already uses, or PyVista, which the PO suggested.

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

How each library fits in our Qt window is described in `gui_qt_integration.md` (#9, SCRUM-28). In short: both can be placed in our window as a normal Qt widget (napari through `QtViewer`, PyVista through pyvistaqt's `QtInteractor`). napari handles the time axis, points of the current frame, track tails and gamma by itself. With PyVista we write those parts: the demo is 174 lines of code against 129 for napari.

## Measures

`demos/bench.py` (draft #10, SCRUM-29) runs the same steps on both demos, each run in a new process: start the program, change frame from the panel, rotate the view with a simulated mouse drag, read the memory. Every step waits until the view is drawn and the GPU has finished. Medians of 5 runs, on a laptop with a Ryzen 7 7730U, an integrated AMD Radeon GPU, 16 GB of RAM and a 60 Hz screen.

| data (one frame) | library | startup | frame change | mouse rotation | RAM |
|---|---|---|---|---|---|
| Crop-02 (11x100x100) | napari | 9.8 s | 68 ms | 60 fps | 560 MB |
| | PyVista | 4.3 s | 36 ms | 21 fps | 612 MB |
| Crop-01 (21x150x150) | napari | 9.9 s | 71 ms | 59 fps | 607 MB |
| | PyVista | 4.4 s | 37 ms | 21 fps | 544 MB |
| random (40x256x256) | napari | 9.0 s | 41 ms | 55 fps | 749 MB |
| | PyVista | 4.3 s | 46 ms | 18 fps | 509 MB |
| random, real size (95x512x512) | napari | 9.8 s | 81 ms | 43 fps | 2392 MB |
| | PyVista | 7.2 s | 159 ms | 13 fps | 672 MB |

What the numbers say:

- **Startup**: PyVista starts in about half the time. Importing napari alone takes 4.5 to 4.9 s.
- **Frame change**: PyVista is faster on the small sample files, but its time grows more with the volume. At real size napari changes frame in 81 ms, so a play at 10 frames per second keeps up, while PyVista needs 159 ms and plays at about 6 frames per second.
- **Rotation**: napari reaches the limit of the screen (60 fps) on small data and keeps 43 fps at real size, PyVista 21 and 13 fps. With the mouse, PyVista draws about 2.3 times for every mouse move (VTK draws, then Qt repaints the widget), napari once.
- **Memory**: napari keeps the frames it has read in a cache (a quarter of the RAM by default, configurable), so at real size it grows to 2.4 GB after 22 frames, and a frame seen before comes back at once. PyVista stays under 700 MB.

## Is it the library or our PyVista code?

We know napari better than PyVista, so we checked whether the PyVista demo was the reason for the gap, on the real-size volume:

- One fix was already applied before the measures: with pyvistaqt, `plotter.render()` drew every change about twice; asking redraws with Qt `update()` brought the frame change on Crop-02 from 76 to 40-50 ms.
- A PyVista frame change at real size splits into reading the frame (21 ms), copying it into VTK (5 ms), points and tracks (7 ms) and drawing (133 ms), which is mostly uploading the new volume to the GPU.
- The other VTK volume mappers are slower: `gpu` and `open_gl` take 321-327 ms per frame change and rotate at about 6 fps. The default `smart` mapper used in the measures is the fastest.
- The double draw per mouse move comes from the way pyvistaqt puts VTK in a `QOpenGLWidget`, chosen to work with Wayland. As an upper bound we let VTK draw by itself, once per step and without Qt: 28.7 fps, still below the 43 fps napari reaches with Qt and the mouse.

So with what we tried the result does not change. napari was not tuned at all, so if anything it has more room to improve.

## Proposal

We propose to keep **napari**, used as a widget (`QtViewer`) inside our own Qt window.

- It is clearly better on what the PO complains about: at real size it changes frame twice as fast and rotates three times more fluidly than PyVista.
- Time series, points of the current frame, tracks and the layer model are built in, so the code is shorter and closer to what the researchers already know.
- Embedding it as a widget keeps our window, menus and panels under our control, as in the GUI base.

Things to handle with napari:

- **Startup of about 10 s**: show our window first and create the napari view right after, so the user sees the application at once; import napari only when it is needed (the CLI never imports it).
- **Memory**: set napari's cache size from our settings, depending on the machine.
- **`QtViewer` as a widget** is less documented than napari's own window: keep it behind one class of ours, pin the napari version and check it when updating.
- The pitfalls found in the demos (active layer for clicks, empty tracks, line widths with the voxel scale) are listed in `gui_qt_integration.md`.

PyVista would be the better choice only if startup time and memory mattered more than fluidity with real volumes, or if we needed general 3D meshes rather than microscopy volumes.

## Limits and next steps

- The numbers are for one laptop with an integrated GPU. The comparison between the two libraries holds, the absolute values will be better on the lab workstation.
- The real-size volume is random data with the right size and type. A real large file has not been tested yet: reading 50 MB per frame with czifile from disk will add to the frame change time of both libraries.
- Next steps if napari is chosen: test a large real file, measure the startup with the window shown before napari is loaded, and choose the cache size.
