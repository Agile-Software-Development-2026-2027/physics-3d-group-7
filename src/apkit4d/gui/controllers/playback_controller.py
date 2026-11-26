"""
Controller of the playback: moves through the frames of a recording.

It connects the playback bar (view) to the position in the recording. It knows how many frames there are
only because someone tells it with `set_frame_count`, and announces every change of the current frame
with `frame_changed`: the 3D view connects to that signal to show the frame. It also keeps the settings
of the playback: the step, that is how many frames are skipped at every move, and the speed.
"""

from PySide6.QtCore import QObject, Qt, QTimer, Signal

from apkit4d.core.frame_range import FrameRange
from apkit4d.gui.constants import playback
from apkit4d.gui.views.playback.playback_bar import PlaybackBar


class PlaybackController(QObject):
    """
    Keeps the current frame and moves it when the user or the playback asks for it.

    Frames are indices starting from 0. Requests outside the recording are limited to the first or the
    last frame, and every move goes from frame k to frame k plus or minus the step.

    Args:
        bar: The playback bar to control.
        parent: Qt parent, so the controller lives as long as its owner.

    Signals:
        frame_changed: Emitted with the new frame every time the current frame changes.
        step_changed: Emitted with the new step every time it changes.
        speed_changed: Emitted with the new speed, in frames per second, every time it changes.
    """

    frame_changed = Signal(int)
    step_changed = Signal(int)
    speed_changed = Signal(float)

    def __init__(self, bar: PlaybackBar, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._frame_range: FrameRange | None = None

        self._bar = bar
        self._frame = 0
        self._frame_count = 0
        self._step = playback.DEFAULT_STEP
        self._speed = playback.DEFAULT_SPEED_FPS

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)  # at many frames per second the error would show
        self._timer.setInterval(self._interval_ms())
        self._timer.timeout.connect(self._on_tick)

        bar.frame_requested.connect(self.go_to_frame)
        bar.previous_requested.connect(self.previous_frame)
        bar.next_requested.connect(self.next_frame)
        bar.play_toggled.connect(self.toggle_playing)
        bar.step_changed.connect(self.set_step)
        bar.speed_changed.connect(self.set_speed)
        bar.set_step(self._step)
        bar.set_speed(self._speed)

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

    @property
    def step(self) -> int:
        """How many frames every move skips."""
        return self._step

    @property
    def speed(self) -> float:
        """Speed of the playback, in frames per second."""
        return self._speed

    def set_frame_count(self, count: int) -> None:
        """
        Tell the controller how many frames the recording has.

        The slider range follows, the current frame and the step are brought back inside what the new
        recording allows, and the playback stops if there is nothing left to play.

        Args:
            count: Number of frames, negative values are treated as 0.
        """
        self._frame_count = max(count, 0)
        self._bar.set_frame_count(self._frame_count)
        self.set_step(self._step)
        self.go_to_frame(self._frame)
        if self._frame_count <= 1:
            self.set_playing(False)

    def go_to_frame(self, frame: int) -> None:
        """Go to frame, limited to the selected frame range."""
        frame = min(max(frame, self._first_frame), self._last_frame)

        if frame == self._frame:
            self._bar.set_frame(frame)
            return

        self._frame = frame
        self._bar.set_frame(frame)
        self.frame_changed.emit(frame)

    def next_frame(self) -> None:
        """Go forward by the step, staying on the last frame if the recording ends before."""
        self.go_to_frame(self._frame + self._step)

    def previous_frame(self) -> None:
        """Go back by the step, staying on the first frame if the recording starts after."""
        self.go_to_frame(self._frame - self._step)

    def toggle_playing(self) -> None:
        """Start the playback if it is stopped, stop it if it is running."""
        self.set_playing(not self.is_playing)

    def set_playing(self, playing: bool) -> None:
        playing = playing and self._last_frame > self._first_frame

        if playing == self.is_playing:
            return

        if playing:
            if self._frame >= self._last_frame:
                self.go_to_frame(self._first_frame)

            self._timer.start()
        else:
            self._timer.stop()

        self._bar.set_playing(playing)

    def set_step(self, step: int) -> None:
        """
        Set how many frames every move skips.

        The step is limited to what the recording allows, from 1 to one less than the number of frames.
        The bar always shows the step that was really applied, which can differ from the one asked.

        Args:
            step: Number of frames to skip.
        """
        step = min(max(int(step), playback.MIN_STEP), self._max_step)
        changed = step != self._step
        self._step = step
        self._bar.set_step(step)
        if changed:
            self.step_changed.emit(step)

    def set_speed(self, speed: float) -> None:
        """
        Set the speed of the playback. It takes effect at once, also while the recording is playing.

        The speed is limited between `MIN_SPEED_FPS` and `MAX_SPEED_FPS`, and the bar shows the one that
        was really applied.

        Args:
            speed: Frames per second.
        """
        speed = min(max(float(speed), playback.MIN_SPEED_FPS), playback.MAX_SPEED_FPS)
        changed = speed != self._speed
        self._speed = speed
        self._timer.setInterval(self._interval_ms())
        self._bar.set_speed(speed)
        if changed:
            self.speed_changed.emit(speed)

    @property
    def _first_frame(self) -> int:
        if self._frame_range is None:
            return 0

        return max(self._frame_range.start, 0)

    @property
    def _last_frame(self) -> int:
        last_recording_frame = max(self._frame_count - 1, 0)

        if self._frame_range is None:
            return last_recording_frame

        return min(self._frame_range.end, last_recording_frame)

    @property
    def _max_step(self) -> int:
        return max(
            self._last_frame - self._first_frame,
            playback.MIN_STEP,
        )

    def _interval_ms(self) -> int:
        return max(1, round(1000 / self._speed))

    def _on_tick(self) -> None:
        if self._frame >= self._last_frame:
            self.set_playing(False)
        else:
            self.next_frame()

    def set_frame_range(self, frame_range: FrameRange | None) -> None:
        self._frame_range = frame_range
        self._bar.set_frame_range(frame_range)

        self.set_step(self._step)
        self.go_to_frame(self._frame)

        if self._last_frame <= self._first_frame:
            self.set_playing(False)
