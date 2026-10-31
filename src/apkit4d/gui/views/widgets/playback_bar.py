"""
Playback bar: slider and buttons to move through the frames of a recording.

The bar holds no logic. It announces what the user asks for with signals, and shows what it is told
with its methods. The controller connects it to the rest of the application. It starts disabled, and
the controller enables it when there is something to play.
"""

from PySide6.QtCore import Qt, Signal, SignalInstance
from PySide6.QtWidgets import QHBoxLayout, QPushButton, QSlider, QVBoxLayout, QWidget

from apkit4d.gui.constants import names, texts


class PlaybackBar(QWidget):
    """
    Bar with a frame slider and, below it, previous, play and next buttons.

    The signals and methods use frame indices starting from 0.

    Signals:
        previous_requested: The user pressed the previous button.
        next_requested: The user pressed the next button.
        play_toggled: The user pressed the play button.
        frame_requested: Emitted with the frame the user chose with the slider.
    """

    previous_requested = Signal()
    next_requested = Signal()
    play_toggled = Signal()
    frame_requested = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName(names.PLAYBACK_BAR)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setObjectName(names.FRAME_SLIDER)
        self._slider.valueChanged.connect(self.frame_requested)

        self._previous_button = self._make_button(
            names.PREVIOUS_BUTTON, texts.BUTTON_PREVIOUS, self.previous_requested
        )
        self._play_button = self._make_button(names.PLAY_BUTTON, texts.BUTTON_PLAY, self.play_toggled)
        self._next_button = self._make_button(names.NEXT_BUTTON, texts.BUTTON_NEXT, self.next_requested)

        buttons = QHBoxLayout()
        for button in (self._previous_button, self._play_button, self._next_button):
            buttons.addWidget(button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._slider)
        layout.addLayout(buttons)

        self.setEnabled(False)  # nothing to play until a file is open

    def set_frame_count(self, count: int) -> None:
        """
        Set the range of the slider for a recording of `count` frames.

        Args:
            count: Number of frames.
        """
        self._slider.blockSignals(True)  # a change made by the program is not a user request
        self._slider.setRange(0, max(count - 1, 0))
        self._slider.blockSignals(False)

    def set_frame(self, frame: int) -> None:
        """
        Move the slider to `frame` without emitting `frame_requested`.

        Args:
            frame: Index of the current frame.
        """
        self._slider.blockSignals(True)
        self._slider.setValue(frame)
        self._slider.blockSignals(False)

    def set_playing(self, playing: bool) -> None:
        """
        Show the play button as "Pause" while the recording is playing, as "Play" otherwise.

        Args:
            playing: True while the playback is running.
        """
        self._play_button.setText(texts.BUTTON_PAUSE if playing else texts.BUTTON_PLAY)

    @staticmethod
    def _make_button(name: str, text: str, signal: SignalInstance) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(name)
        button.clicked.connect(signal)
        return button
