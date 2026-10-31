"""
Controller of the playback: moves through the frames of a recording.

It connects the playback bar (view) to the position in the recording. It knows how many frames
there are only because someone tells it with `set_frame_count`, and announces every change of
the current frame with `frame_changed`: the 3D view connects to that signal to show the frame.
"""

from PySide6.QtCore import QObject, QTimer, Signal

from apkit4d.gui import constants
from apkit4d.gui.playback_bar import PlaybackBar


class PlaybackController(QObject):
    """
    Keeps the current frame and moves it when the user or the playback asks for it.

    Frames are indices starting from 0. Requests outside the recording are limited to
    the first or the last frame.

    Args:
        bar: The playback bar to control.
        parent: Qt parent, so the controller lives as long as the bar.

    Signals:
        frame_changed: Emitted with the new frame every time the current frame changes.
    """

    frame_changed = Signal(int)

    def __init__(self, bar: PlaybackBar, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._bar = bar
        self._frame = 0
        self._frame_count = 0

        self._timer = QTimer(self)
        self._timer.setInterval(constants.FRAME_INTERVAL_MS)
        self._timer.timeout.connect(self._on_tick)

        bar.frame_requested.connect(self.go_to_frame)
        bar.previous_requested.connect(self.previous_frame)
        bar.next_requested.connect(self.next_frame)
        bar.play_toggled.connect(self.toggle_playing)

    @property
    def frame(self) -> int:
        """Index of the current frame."""
        return self._frame

    @property
    def frame_count(self) -> int:
        """Number of frames of the recording, 0 if there is none."""
        return self._frame_count

    @property
    def is_playing(self) -> bool:
        """True while the playback is running."""
        return self._timer.isActive()

    def set_frame_count(self, count: int) -> None:
        """
        Tell the controller how many frames the recording has.

        The slider range follows, the current frame is brought back inside the new range,
        and the playback stops if there is nothing left to play.

        Args:
            count: Number of frames, negative values are treated as 0.
        """
        self._frame_count = max(count, 0)
        self._bar.set_frame_count(self._frame_count)
        self.go_to_frame(self._frame)
        if self._frame_count <= 1:
            self.set_playing(False)

    def go_to_frame(self, frame: int) -> None:
        """
        Go to `frame`, limited to the first and the last frame.

        Args:
            frame: Index of the wanted frame.
        """
        frame = min(max(frame, 0), self._last_frame)
        if frame == self._frame:
            return
        self._frame = frame
        self._bar.set_frame(frame)
        self.frame_changed.emit(frame)

    def next_frame(self) -> None:
        """Go to the next frame, staying on the last one if already there."""
        self.go_to_frame(self._frame + 1)

    def previous_frame(self) -> None:
        """Go to the previous frame, staying on the first one if already there."""
        self.go_to_frame(self._frame - 1)

    def toggle_playing(self) -> None:
        """Start the playback if it is stopped, stop it if it is running."""
        self.set_playing(not self.is_playing)

    def set_playing(self, playing: bool) -> None:
        """
        Start or stop the playback. Starting is ignored if there is only one frame or none.

        Starting from the last frame goes back to the first one, as video players do.

        Args:
            playing: True to start, False to stop.
        """
        playing = playing and self._frame_count > 1
        if playing == self.is_playing:
            return
        if playing:
            if self._frame >= self._last_frame:
                self.go_to_frame(0)
            self._timer.start()
        else:
            self._timer.stop()
        self._bar.set_playing(playing)

    @property
    def _last_frame(self) -> int:
        return max(self._frame_count - 1, 0)

    def _on_tick(self) -> None:
        if self._frame >= self._last_frame:
            self.set_playing(False)
        else:
            self.next_frame()
