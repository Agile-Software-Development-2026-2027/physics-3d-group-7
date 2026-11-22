"""
Playback bar: slider and buttons to move through the frames of a recording.

The bar holds no logic. It announces what the user asks for with signals, and shows what it is told
with its methods. The controller connects it to the rest of the application. It starts disabled, and
the controller enables it when there is something to play.
"""

from typing import override

from PySide6.QtCore import QSize, Signal, SignalInstance
from PySide6.QtGui import QPalette, QResizeEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLayout, QVBoxLayout, QWidget

from apkit4d.gui.constants import appearance, names, playback, texts
from apkit4d.gui.views.playback.frame_counter import FrameCounter
from apkit4d.gui.views.widgets.divider import Divider
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.gui.views.widgets.icon_button import IconButton
from apkit4d.gui.views.widgets.icons import Icon
from apkit4d.gui.views.widgets.labeled_button import LabeledButton
from apkit4d.gui.views.widgets.number_stepper import NumberStepper
from apkit4d.gui.views.widgets.wheel_guard import install_wheel_guard


class PlaybackBar(QWidget):
    """
    Bar with a frame slider and, below it, the buttons and the settings of the playback.

    The signals and methods use frame indices starting from 0.

    When the bar is too narrow for everything it holds, it simplifies itself in two steps. First the caption
    of the speed disappears, because its unit already says what it is. Then the caption of the step
    disappears too and the button that resets the camera shows only its icon. The narrowest the bar can be
    is the width of the last step, so that the columns of the window can be resized freely.

    Signals:
        previous_requested: The user pressed the previous button.
        next_requested: The user pressed the next button.
        play_toggled: The user pressed the play button.
        frame_requested: Emitted with the frame the user chose with the slider.
        step_changed: Emitted with the number of frames to skip, when the user changes it.
        speed_changed: Emitted with the speed in frames per second, when the user changes it.
        reset_camera_requested: The user pressed the button that resets the camera.
    """

    previous_requested = Signal()
    next_requested = Signal()
    play_toggled = Signal()
    frame_requested = Signal(int)
    step_changed = Signal(int)
    speed_changed = Signal(float)
    reset_camera_requested = Signal()

    # defaults of the class: Qt can ask for the size of the bar, or resize it, before `__init__` has ended
    _level: int = 0  # 0 shows everything, 2 is the most compact form
    _widths: tuple[int, int, int] = (0, 0, 0)  # the narrowest bar that can show each level

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName(names.PLAYBACK_BAR)

        self._slider = FrameSlider()
        self._slider.setObjectName(names.FRAME_SLIDER)
        self._slider.valueChanged.connect(self.frame_requested)

        self._previous_button = self._make_button(
            names.PREVIOUS_BUTTON,
            texts.BUTTON_PREVIOUS,
            texts.TOOLTIP_PREVIOUS,
            Icon.PREVIOUS,
            self.previous_requested,
        )
        self._play_button = self._make_button(
            names.PLAY_BUTTON,
            texts.BUTTON_PLAY,
            texts.TOOLTIP_PLAY,
            Icon.PLAY,
            self.play_toggled,
            primary=True,
        )
        self._next_button = self._make_button(
            names.NEXT_BUTTON, texts.BUTTON_NEXT, texts.TOOLTIP_NEXT, Icon.NEXT, self.next_requested
        )

        self._counter = FrameCounter()

        self._speed = NumberStepper(
            width=appearance.SPEED_STEPPER_WIDTH,
            decimals=playback.SPEED_DECIMALS,
            step=playback.SPEED_STEP_FPS,
            suffix=texts.SUFFIX_SPEED,
        )
        self._speed.setObjectName(names.SPEED_FIELD)
        self._speed.setToolTip(texts.TOOLTIP_SPEED)
        self._speed.set_range(playback.MIN_SPEED_FPS, playback.MAX_SPEED_FPS)
        self._speed.set_value(playback.DEFAULT_SPEED_FPS)
        self._speed.value_changed.connect(self.speed_changed)

        self._step = NumberStepper(width=appearance.STEP_STEPPER_WIDTH, decimals=0, step=1)
        self._step.setObjectName(names.STEP_FIELD)
        self._step.setToolTip(texts.TOOLTIP_STEP)
        self._step.set_range(playback.MIN_STEP, playback.MIN_STEP)
        self._step.set_value(playback.DEFAULT_STEP)
        self._step.value_changed.connect(self._on_step_edited)

        self._reset_button = LabeledButton(Icon.RESET, texts.BUTTON_RESET_CAMERA)
        self._reset_button.setObjectName(names.RESET_CAMERA_BUTTON)
        self._reset_button.setToolTip(texts.TOOLTIP_RESET_CAMERA)
        self._reset_button.clicked.connect(self.reset_camera_requested)

        self._speed_caption = self._caption(texts.LABEL_SPEED)
        self._step_caption = self._caption(texts.LABEL_STEP)

        row = QHBoxLayout()
        row.setSpacing(appearance.BAR_ITEMS_SPACING)
        for button in (self._previous_button, self._play_button, self._next_button):
            row.addWidget(button)
        row.addSpacing(appearance.COUNTER_SPACING)
        row.addWidget(self._counter)
        row.addStretch(1)
        row.addWidget(self._speed_caption)
        row.addWidget(self._speed)
        self._add_divider(row)
        row.addWidget(self._step_caption)
        row.addWidget(self._step)
        self._add_divider(row)
        row.addWidget(self._reset_button)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(*appearance.BAR_MARGINS)
        layout.setSpacing(appearance.BAR_ROWS_SPACING)
        layout.addWidget(self._slider)
        layout.addLayout(row)
        self._row = row
        layout.setSizeConstraint(
            QLayout.SizeConstraint.SetNoConstraint
        )  # the width is decided by minimumSizeHint
        self._layout = layout

        self._measure_widths()

        self.setEnabled(False)  # nothing to play until a file is open
        self._wheel_guard = install_wheel_guard(self)

    def set_frame_count(self, count: int) -> None:
        """
        Set the range of the slider and the largest step for a recording of `count` frames.

        Args:
            count: Number of frames.
        """
        self._slider.blockSignals(True)  # a change made by the program is not a user request
        self._slider.setRange(0, max(count - 1, 0))
        self._slider.blockSignals(False)
        self._counter.set_frame_count(count)
        self._step.set_range(playback.MIN_STEP, max(count - 1, playback.MIN_STEP))
        self._measure_widths()  # the counter is wider with more frames

    def set_frame(self, frame: int) -> None:
        """
        Move the slider to `frame` without emitting `frame_requested`.

        Args:
            frame: Index of the current frame.
        """
        self._slider.blockSignals(True)
        self._slider.setValue(frame)
        self._slider.blockSignals(False)
        self._counter.set_frame(frame)

    def set_step(self, step: int) -> None:
        """
        Show `step` as the number of frames to skip, without emitting `step_changed`.

        Args:
            step: Number of frames.
        """
        self._step.set_value(step)

    def set_speed(self, speed: float) -> None:
        """
        Show `speed` as the speed of the playback, without emitting `speed_changed`.

        Args:
            speed: Frames per second.
        """
        self._speed.set_value(speed)

    def set_playing(self, playing: bool) -> None:
        """
        Show the play button as a pause button while the recording is playing, as a play button otherwise.

        Args:
            playing: True while the playback is running.
        """
        self._play_button.setText(texts.BUTTON_PAUSE if playing else texts.BUTTON_PLAY)
        self._play_button.setToolTip(texts.TOOLTIP_PAUSE if playing else texts.TOOLTIP_PLAY)
        self._play_button.set_icon_kind(Icon.PAUSE if playing else Icon.PLAY)

    @override
    def minimumSizeHint(self) -> QSize:
        return QSize(self._widths[2], self._layout.minimumSize().height())

    @override
    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        width = event.size().width()
        self._set_level(0 if width >= self._widths[0] else 1 if width >= self._widths[1] else 2)

    def _set_level(self, level: int) -> None:
        if level == self._level:
            return
        self._level = level
        self._speed_caption.setVisible(level == 0)
        self._step_caption.setVisible(level <= 1)
        self._reset_button.set_compact(level == 2)
        self._invalidate_layouts()

    def _invalidate_layouts(self) -> None:
        """Make both layouts measure their items again: the row keeps its own cache."""
        self._row.invalidate()
        self._layout.invalidate()

    def _measure_widths(self) -> None:
        """Measure how wide the bar must be to show each level, which depends for example on the counter."""
        level = self._level
        widths = []
        for candidate in (0, 1, 2):
            self._set_level(candidate)
            self._invalidate_layouts()
            widths.append(self._layout.minimumSize().width())
        self._widths = (widths[0], widths[1], widths[2])
        self._set_level(level)
        self._invalidate_layouts()
        self.updateGeometry()

    def _on_step_edited(self, value: float) -> None:
        self.step_changed.emit(round(value))

    @staticmethod
    def _caption(text: str) -> QLabel:
        label = QLabel(text)
        label.setForegroundRole(QPalette.ColorRole.PlaceholderText)  # a quiet color, in every theme
        return label

    @staticmethod
    def _add_divider(row: QHBoxLayout) -> None:
        row.addSpacing(appearance.GROUP_SPACING)
        row.addWidget(Divider())
        row.addSpacing(appearance.GROUP_SPACING)

    @staticmethod
    def _make_button(
        name: str, text: str, tooltip: str, icon: Icon, signal: SignalInstance, *, primary: bool = False
    ) -> IconButton:
        size = appearance.PLAY_BUTTON_SIZE if primary else appearance.TRANSPORT_BUTTON_SIZE
        icon_size = appearance.PLAY_ICON_SIZE if primary else appearance.TRANSPORT_ICON_SIZE
        button = IconButton(icon, size, icon_size, primary=primary)
        button.setObjectName(name)
        button.setText(text)  # not drawn, but kept for the tools that read the interface aloud
        button.setToolTip(tooltip)
        button.clicked.connect(signal)
        return button
