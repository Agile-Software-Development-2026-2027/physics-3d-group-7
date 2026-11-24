"""
Number that can be typed, with a button to decrease it and a button to increase it.
"""

from typing import override

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontDatabase, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QAbstractSpinBox, QDoubleSpinBox, QHBoxLayout, QWidget

from apkit4d.gui.constants import appearance, texts
from apkit4d.gui.theme.colors import focus_pen, plain_button_colors
from apkit4d.gui.views.widgets.icon_button import IconButton
from apkit4d.gui.views.widgets.icons import Icon
from apkit4d.gui.views.widgets.wheel_guard import install_wheel_guard

ColorRole = QPalette.ColorRole


class NumberStepper(QWidget):
    """
    A rounded frame with a minus button, a number that can be typed and a plus button.

    The value changes when a button is pressed, when the wheel turns over the number while holding
    Ctrl or Shift, and when the user types a number and confirms it. A value outside the range is brought
    back inside it. With no decimals it is a whole number.

    Args:
        width: Width of the whole widget.
        decimals: How many decimals the number has.
        step: How much the buttons add or subtract.
        suffix: Text shown after the number, for example the unit.
        parent: Qt parent.

    Signals:
        value_changed: Emitted with the new value when the user changes it.
    """

    value_changed = Signal(float)
    _focused: bool = False  # a default of the class: a handler can run on an instance that Python has emptied

    def __init__(
        self, *, width: int, decimals: int, step: float, suffix: str = "", parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.setFixedSize(width, appearance.STEPPER_HEIGHT)

        self._spin = QDoubleSpinBox()
        self._spin.setDecimals(decimals)
        self._spin.setSingleStep(step)
        self._spin.setSuffix(suffix)
        self._spin.setButtonSymbols(QAbstractSpinBox.ButtonSymbols.NoButtons)
        self._spin.setFrame(False)
        self._spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._spin.setKeyboardTracking(False)  # the value changes when it is confirmed, not at every key
        self._spin.setFocusPolicy(Qt.FocusPolicy.StrongFocus)  # the wheel acts only after a click on it
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSizeF(appearance.STEPPER_FONT_POINTS)
        font.setWeight(QFont.Weight.DemiBold)
        self._spin.setFont(font)
        palette = self._spin.palette()
        palette.setColor(ColorRole.Base, QColor(0, 0, 0, 0))  # the frame of this widget is the background
        self._spin.setPalette(palette)
        self._spin.installEventFilter(self)
        self._spin.valueChanged.connect(self.value_changed)

        minus = self._make_button(Icon.MINUS, texts.TOOLTIP_DECREASE, self._spin.stepDown)
        plus = self._make_button(Icon.PLUS, texts.TOOLTIP_INCREASE, self._spin.stepUp)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(3, 0, 3, 0)
        layout.setSpacing(0)
        layout.addWidget(minus)
        layout.addWidget(self._spin, 1)
        layout.addWidget(plus)
        self._wheel_guard = install_wheel_guard(self)

    def value(self) -> float:
        """The number that is shown."""
        return self._spin.value()

    def set_value(self, value: float) -> None:
        """
        Show `value` without emitting `value_changed`.

        Args:
            value: The number to show. A value outside the range is brought back inside it.
        """
        self._spin.blockSignals(True)
        self._spin.setValue(value)
        self._spin.blockSignals(False)

    def set_range(self, minimum: float, maximum: float) -> None:
        """
        Set the smallest and the largest value, without emitting `value_changed`.

        Args:
            minimum: Smallest value.
            maximum: Largest value.
        """
        self._spin.blockSignals(True)
        self._spin.setRange(minimum, maximum)
        self._spin.blockSignals(False)

    @override
    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is self._spin and event.type() in (QEvent.Type.FocusIn, QEvent.Type.FocusOut):
            self._focused = event.type() == QEvent.Type.FocusIn
            self.update()
        return super().eventFilter(watched, event)

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        background, border, _ink = plain_button_colors(
            palette, enabled=self.isEnabled(), down=False, hovered=False
        )
        inset = appearance.FOCUS_RING_WIDTH / 2 if self._focused else 0.5
        shape = self.rect().toRectF().adjusted(inset, inset, -inset, -inset)
        painter.setBrush(background)
        painter.setPen(focus_pen(palette) if self._focused else border)
        painter.drawRoundedRect(shape, appearance.BUTTON_RADIUS, appearance.BUTTON_RADIUS)

    @staticmethod
    def _make_button(icon: Icon, tooltip: str, slot) -> IconButton:
        button = IconButton(icon, appearance.STEPPER_BUTTON_SIZE, appearance.STEPPER_ICON_SIZE, flat=True)
        button.setToolTip(tooltip)
        button.setAutoRepeat(True)  # holding the button keeps changing the value
        button.clicked.connect(slot)
        return button
