from typing import Self

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QSpinBox, QWidget

from apkit4d.core.frame_range import FrameRange
from apkit4d.gui.constants import texts


class FramesSelector(QWidget):
    selected_frames_confirmed = Signal(object)

    def __init__(
        self,
        frame_range: FrameRange | None,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)

        self._frame_range: FrameRange | None = None
        self._selected_frames: FrameRange | None = None
        self._disabled = False

        self._end_frame = QSpinBox()
        self._start_frame = QSpinBox()

        self.set_frame_range(frame_range, True)

        self._start_frame.editingFinished.connect(self._on_start_frame_confirmed)
        self._end_frame.editingFinished.connect(self._on_end_frame_confirmed)

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

    @property
    def selected_frames(self) -> FrameRange | None:
        return self._selected_frames

    def disable(self, disabled: bool = True):
        self._disabled = disabled
        self._start_frame.setDisabled(disabled)
        self._end_frame.setDisabled(disabled)

    def set_selected_frames(self, start: int | None = None, end: int | None = None):
        """Select frames programmatically, clamped to the bounds.

        Args:
            start: First frame as the user sees it (one-based), or None to keep the current one.
            end: Last frame as the user sees it (one-based), or None to keep the current one.

        Emits:
            selected_frames_confirmed: With the new zero-based selection.
        """
        if self._selected_frames is None or self._frame_range is None:
            return

        selection = self._selected_frames
        if start is not None:
            selection = selection.with_start(start - 1)
        if end is not None:
            selection = selection.with_end(end - 1)

        selection = selection.clamp(self._frame_range)

        self._start_frame.blockSignals(True)
        self._start_frame.setValue(selection.start_display)
        self._start_frame.blockSignals(False)

        self._end_frame.blockSignals(True)
        self._end_frame.setValue(selection.end_display)
        self._end_frame.blockSignals(False)

        self._selected_frames = selection
        self.selected_frames_confirmed.emit(selection)

    def set_frame_range(
        self,
        frame_range: FrameRange | None,
        adjust_frames: bool = False,
    ):
        """Update the widget's frame bounds and the selection within them.

        Args:
            frame_range: The new bounds (zero-based, inclusive), or `None` when no frames
                are available. When `None`, both spinboxes are locked to `0` with their
                special value placeholder active and there is no selection.
            adjust_frames: If `True`, select the whole range. If `False`, keep the current
                selection, clamped within the new bounds.

        Emits:
            selected_frames_confirmed: With the new selection, when `adjust_frames` is `True`
                or the clamping changed the selection.
            frame_range_changed: Always, with the current selection (or `None`).
        """
        self._frame_range = frame_range

        if frame_range is None:
            self.disable()

            special_value_text = "—"
            self._start_frame.setSpecialValueText(special_value_text)
            self._end_frame.setSpecialValueText(special_value_text)

            self._start_frame.setRange(0, 0)
            self._end_frame.setRange(0, 0)
            self._start_frame.setValue(0)
            self._end_frame.setValue(0)

            self._selected_frames = None
            self.selected_frames_confirmed.emit(None)
            return

        self.disable(False)

        self._start_frame.setSpecialValueText("")
        self._end_frame.setSpecialValueText("")

        self._start_frame.setRange(frame_range.start_display, frame_range.end_display)
        self._end_frame.setRange(frame_range.start_display, frame_range.end_display)

        previous = self._selected_frames
        if adjust_frames or previous is None:
            selection = FrameRange(frame_range.start, frame_range.end)
        else:
            # Clamping both ends into the new bounds
            selection = previous.clamp(frame_range)

        self._selected_frames = selection
        self._start_frame.setValue(selection.start_display)
        self._end_frame.setValue(selection.end_display)

        if adjust_frames or selection != previous:
            self.selected_frames_confirmed.emit(selection)

    def _on_start_frame_confirmed(self):
        if self._selected_frames is None:
            return

        self.set_selected_frames(self._start_frame.value(), self._end_frame.value())

    def _on_end_frame_confirmed(self):
        if self._selected_frames is None:
            return

        self.set_selected_frames(self._start_frame.value(), self._end_frame.value())
