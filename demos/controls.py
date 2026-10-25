"""
Side panel shared by the GUI demos: the same controls for every library, so the
comparison only changes the 3D view.

The panel knows nothing about napari or PyVista. It only emits signals, and each
demo connects them to its own view.
"""

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFormLayout, QPushButton, QWidget
from superqt import QLabeledDoubleSlider, QLabeledRangeSlider, QLabeledSlider

PLAY_FPS: int = 10


class ControlPanel(QWidget):
    """
    Frame slider with play/pause, contrast range and gamma.

    Signals:
        frame_changed: The frame to show.
        contrast_changed: The new (min, max) intensity of the contrast.
        gamma_changed: The new gamma.
    """

    frame_changed = Signal(int)
    contrast_changed = Signal(int, int)
    gamma_changed = Signal(float)

    def __init__(self, n_frames: int, max_intensity: int, contrast: tuple[int, int]) -> None:
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

        layout = QFormLayout(self)
        layout.addRow("Frame", self.frame)
        layout.addRow("", self.play)
        layout.addRow("Contrast", self.contrast)
        layout.addRow("Gamma", self.gamma)

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

    def _next_frame(self) -> None:
        self.frame.setValue((self.frame.value() + 1) % (self.frame.maximum() + 1))
