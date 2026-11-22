"""Mouse-wheel guard preventing accidental input edits while scrolling panels."""

from typing import override

from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea,
    QAbstractSpinBox,
    QComboBox,
    QDial,
    QSlider,
    QWidget,
)

GUARDED_INPUT_TYPES = (QAbstractSpinBox, QSlider, QDial, QComboBox)


class WheelGuard(QObject):
    """Block unmodified wheel events on input controls while preserving scroll-area scrolling.

    Guards spinboxes, sliders, dials, and dropdowns (`QComboBox`). Wheel adjustment remains
    available when holding ``Ctrl`` or ``Shift``.
    """

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._forwarding = False

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self._forwarding or event.type() != QEvent.Type.Wheel:
            return super().eventFilter(watched, event)

        if not isinstance(watched, GUARDED_INPUT_TYPES):
            return super().eventFilter(watched, event)

        if isinstance(event, QWheelEvent) and (
            event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier)
        ):
            return super().eventFilter(watched, event)

        event.ignore()
        if isinstance(watched, QWidget):
            scroll_area = self._find_enclosing_scroll_area(watched)
            if scroll_area is not None:
                self._forwarding = True
                try:
                    QCoreApplication.sendEvent(scroll_area.viewport(), event)
                finally:
                    self._forwarding = False
        return True

    @staticmethod
    def _find_enclosing_scroll_area(widget: QWidget) -> QAbstractScrollArea | None:
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QAbstractScrollArea):
                return parent
            parent = parent.parentWidget()
        return None


def install_wheel_guard(root: QWidget) -> WheelGuard:
    """Install a shared wheel guard on spinboxes, sliders, dials, and dropdowns under ``root``."""
    guard = WheelGuard(root)
    for widget_type in GUARDED_INPUT_TYPES:
        for child in root.findChildren(widget_type):
            child.installEventFilter(guard)
    return guard
