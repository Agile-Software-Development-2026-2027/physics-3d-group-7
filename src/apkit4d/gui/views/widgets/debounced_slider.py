from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import QWidget

from apkit4d.gui.views.widgets.frame_slider import FrameSlider


class DebouncedSlider(FrameSlider):
    """
    Our FrameSlider with a custom debounce, so that we avoid
    emitting 329 signals in the blink of an eye.

    Connect to `self.value_debounced`.

    Args:
        delay_ms: minimum delay in milliseconds between emission of signals.
        parent: parent QT widget
    """

    value_debounced = Signal(int)

    def __init__(
        self,
        delay_ms: int = 200,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self._debounce_timer = QTimer(self)
        self._debounce_timer.setSingleShot(True)
        self._debounce_timer.setInterval(delay_ms)

        self.valueChanged.connect(lambda _: self._debounce_timer.start())
        self.sliderReleased.connect(self._flush_debounce)
        self._debounce_timer.timeout.connect(self._emit_debounced)

    def _emit_debounced(self) -> None:
        self.value_debounced.emit(self.value())

    def _flush_debounce(self) -> None:
        if self._debounce_timer.isActive():
            self._debounce_timer.stop()
            self.value_debounced.emit(self.value())
