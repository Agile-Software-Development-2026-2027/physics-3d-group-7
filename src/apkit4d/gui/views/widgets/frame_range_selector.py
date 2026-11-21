from copy import copy
from typing import Self

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSpinBox, QWidget

from apkit4d.gui.constants import texts
from apkit4d.gui.models.frame_range import FrameRange


class FrameRangeSelector(QWidget):
    _MAX_INT32 = 2**31 - 1

    start_frame_changed = Signal(int)
    end_frame_changed = Signal(int)
    frame_range_changed = Signal(FrameRange)

    def __init__(self, start_frame: int = 0, end_frame: int = 0, parent: QWidget | None = None):
        super().__init__(parent)
        self._frame_range = FrameRange(start_frame, end_frame)

        self._start_frame = QSpinBox()
        self._start_frame.setRange(0, self._MAX_INT32)
        self._start_frame.setValue(self._frame_range.first)
        self._start_frame.valueChanged.connect(self._on_start_frame_change)

        self._end_frame = QSpinBox()
        self._end_frame.setRange(0, self._MAX_INT32)
        self._end_frame.setValue(self._frame_range.last)
        self._end_frame.valueChanged.connect(self._on_end_frame_change)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        layout.addWidget(QLabel(texts.START_FRAME_LABEL), alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._start_frame)
        layout.addWidget(QLabel(texts.END_FRAME_LABEL), alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self._end_frame)

    @classmethod
    def from_frame_range(cls, frame_range: FrameRange, parent: QWidget | None = None) -> Self:
        return cls(frame_range.first, frame_range.last, parent)

    def _on_start_frame_change(self, frame: int):
        self._frame_range.first = frame
        self._end_frame.setValue(self._frame_range.last)

        self.start_frame_changed.emit(frame)
        self.frame_range_changed.emit(copy(self._frame_range))

    def _on_end_frame_change(self, frame: int):
        self._frame_range.last = frame
        self._start_frame.setValue(self._frame_range.first)

        self.end_frame_changed.emit(frame)
        self.frame_range_changed.emit(copy(self._frame_range))
