from typing import Self

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSpinBox, QWidget

from apkit4d.core.frame_range import FrameRange
from apkit4d.gui.constants import texts


class FramesSelector(QWidget):
    selected_frames_changed = Signal(object)
    frame_range_changed = Signal(object)

    def __init__(
        self,
        frame_range: FrameRange | None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self._frame_range: FrameRange | None = None
        self._disabled = False

        self._end_frame = QSpinBox()
        self._start_frame = QSpinBox()

        self.set_frame_range(frame_range, True)

        self._end_frame.valueChanged.connect(self._on_end_frame_change)
        self._start_frame.valueChanged.connect(self._on_start_frame_change)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        start_label = QLabel(texts.START_FRAME_LABEL)
        start_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(start_label)
        layout.addWidget(self._start_frame)

        layout.addSpacing(8)

        end_label = QLabel(texts.END_FRAME_LABEL)
        end_label.setSizePolicy(
            QSizePolicy.Policy.Fixed,
            QSizePolicy.Policy.Preferred,
        )
        layout.addWidget(end_label)
        layout.addWidget(self._end_frame)

    @classmethod
    def from_frames(
        cls,
        start_frame: int,
        end_frame: int,
        parent: QWidget | None = None,
    ) -> Self:
        return cls(FrameRange(start_frame, end_frame), parent)

    def _on_start_frame_change(self, frame: int):
        if self._frame_range is None:
            return

        if frame > self._end_frame.value():
            self._end_frame.blockSignals(True)
            self._end_frame.setValue(frame)
            self._end_frame.blockSignals(False)
        else:
            self._frame_range = self._frame_range.with_start(frame)

        self.selected_frames_changed.emit(FrameRange(frame - 1, self._end_frame.value() - 1))

    def _on_end_frame_change(self, frame: int):
        if self._frame_range is None:
            return

        if frame < self._start_frame.value():
            self._start_frame.blockSignals(True)
            self._start_frame.setValue(frame)
            self._start_frame.blockSignals(False)
        else:
            self._frame_range = self._frame_range.with_end(frame)

        self.selected_frames_changed.emit(FrameRange(self._start_frame.value() - 1, frame - 1))

    def _update_enabled_state(self):
        disabled = self._disabled or self._frame_range is None

        special_value_text = "—" if disabled else ""

        self._start_frame.setSpecialValueText(special_value_text)
        self._end_frame.setSpecialValueText(special_value_text)

        self._start_frame.setDisabled(disabled)
        self._end_frame.setDisabled(disabled)

    def disable(self, disabled: bool = True):
        self._disabled = disabled
        self._update_enabled_state()

    def set_frame_range(
        self,
        frame_range: FrameRange | None,
        adjust_frames: bool = False,
    ):
        self._frame_range = frame_range

        if frame_range is None:
            # No frames available: show the special value "—".
            self._start_frame.setRange(0, 0)
            self._end_frame.setRange(0, 0)

            self._start_frame.setValue(0)
            self._end_frame.setValue(0)

            self.selected_frames_changed.emit(None)

        else:
            self._start_frame.setSpecialValueText("")
            self._end_frame.setSpecialValueText("")

            self._start_frame.setRange(
                frame_range.start_display,
                frame_range.end_display,
            )
            self._end_frame.setRange(
                frame_range.start_display,
                frame_range.end_display,
            )

            if adjust_frames:
                self._start_frame.setValue(frame_range.start_display)
                self._end_frame.setValue(frame_range.end_display)

        self._update_enabled_state()
        self.frame_range_changed.emit(frame_range)
