"""
Side panel shared by the GUI demos: the same controls for every library, so the
comparison only changes the 3D view.

The panel knows nothing about napari or PyVista. It only emits signals, and each
demo connects them to its own view.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QCheckBox, QFormLayout, QPushButton, QWidget
from superqt import QLabeledDoubleSlider, QLabeledRangeSlider, QLabeledSlider

PLAY_FPS: int = 10


class ControlPanel(QWidget):
    """
    Frame slider with play/pause, contrast range, gamma and the overlays to show.

    Signals:
        frame_changed: The frame to show.
        contrast_changed: The new (min, max) intensity of the contrast.
        gamma_changed: The new gamma.
        points_toggled: Whether the points are shown.
        tracks_toggled: Whether the tracks are shown.
        roi_toggled: Whether the ROI box is shown.
        roi_changed: The new ROI as z0, z1, y0, y1, x0, x1 in voxels.
    """

    frame_changed = Signal(int)
    contrast_changed = Signal(int, int)
    gamma_changed = Signal(float)
    points_toggled = Signal(bool)
    tracks_toggled = Signal(bool)
    roi_toggled = Signal(bool)
    roi_changed = Signal(int, int, int, int, int, int)

    def __init__(
        self,
        n_frames: int,
        frame_shape: tuple[int, int, int],
        max_intensity: int,
        contrast: tuple[int, int],
        has_points: bool,
        has_tracks: bool,
    ) -> None:
        super().__init__()

        self.frame = QLabeledSlider(Qt.Orientation.Horizontal)
        self.frame.setObjectName("frame_slider")
        self.frame.setRange(0, n_frames - 1)
        self.frame.valueChanged.connect(self.frame_changed)

        self.play = QPushButton("Play")
        self.play.setObjectName("play_button")
        self.play.setCheckable(True)
        self.play.toggled.connect(self._toggle_play)
        self._timer = QTimer(self)
        self._timer.setInterval(1000 // PLAY_FPS)
        self._timer.timeout.connect(self._next_frame)

        self.contrast = QLabeledRangeSlider(Qt.Orientation.Horizontal)
        self.contrast.setObjectName("contrast_slider")
        self.contrast.setRange(0, max_intensity)
        self.contrast.setValue(contrast)
        self.contrast.valueChanged.connect(lambda limits: self.contrast_changed.emit(*limits))

        self.gamma = QLabeledDoubleSlider(Qt.Orientation.Horizontal)
        self.gamma.setObjectName("gamma_slider")
        self.gamma.setRange(0.2, 3.0)
        self.gamma.setValue(1.0)
        self.gamma.valueChanged.connect(self.gamma_changed)

        # disabled when the data has no points or tracks (a .czi file without the legacy outputs)
        self.points = QCheckBox("Points")
        self.points.setObjectName("points_checkbox")
        self.points.setChecked(has_points)
        self.points.setEnabled(has_points)
        self.points.toggled.connect(self.points_toggled)

        self.tracks = QCheckBox("Tracks")
        self.tracks.setObjectName("tracks_checkbox")
        self.tracks.setChecked(has_tracks)
        self.tracks.setEnabled(has_tracks)
        self.tracks.toggled.connect(self.tracks_toggled)

        self.roi = QCheckBox("ROI box")
        self.roi.setObjectName("roi_checkbox")
        self.roi.setChecked(True)
        self.roi.toggled.connect(self.roi_toggled)

        # one range slider per axis; the default ROI is the central half in y and x, all of z
        self.roi_ranges: list[QLabeledRangeSlider] = []
        for axis, size in zip("zyx", frame_shape, strict=True):
            limits = QLabeledRangeSlider(Qt.Orientation.Horizontal)
            limits.setObjectName(f"roi_{axis}_slider")
            limits.setRange(0, size)
            limits.setValue((0, size) if axis == "z" else (size // 4, 3 * size // 4))
            limits.valueChanged.connect(self._emit_roi)
            self.roi_ranges.append(limits)

        layout = QFormLayout(self)
        layout.addRow("Frame", self.frame)
        layout.addRow("", self.play)
        layout.addRow("Contrast", self.contrast)
        layout.addRow("Gamma", self.gamma)
        layout.addRow("Show", self.points)
        layout.addRow("", self.tracks)
        layout.addRow("", self.roi)
        for axis, limits in zip("zyx", self.roi_ranges, strict=True):
            layout.addRow(f"ROI {axis}", limits)

    def roi_bounds(self) -> tuple[int, int, int, int, int, int]:
        """
        The current ROI as z0, z1, y0, y1, x0, x1 in voxels.
        """
        (z0, z1), (y0, y1), (x0, x1) = (limits.value() for limits in self.roi_ranges)
        return z0, z1, y0, y1, x0, x1

    def show_frame(self, t: int) -> None:
        """
        Move the slider to frame `t` without emitting `frame_changed`.

        For when the view changes frame on its own (for example with the keyboard).

        Args:
            t: The frame shown by the view.
        """
        self.frame.blockSignals(True)
        self.frame.setValue(t)
        self.frame.blockSignals(False)

    def _toggle_play(self, playing: bool) -> None:
        self.play.setText("Pause" if playing else "Play")
        if playing:
            self._timer.start()
        else:
            self._timer.stop()

    def _emit_roi(self) -> None:
        self.roi_changed.emit(*self.roi_bounds())

    def _next_frame(self) -> None:
        self.frame.setValue((self.frame.value() + 1) % (self.frame.maximum() + 1))
