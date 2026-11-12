from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts


class TrajectoryLinkingInspector(QWidget):
    """Inspector widget for configuring trajectory linking parameters."""

    min_len_changed: Signal = Signal(int)
    max_gap_changed: Signal = Signal(int)
    max_speed_changed: Signal = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(12)

        group = QGroupBox(texts.INSPECTOR_SECTION_TRACKING_PARAMETERS)
        group.setObjectName(names.TRACKING_INSPECTOR_PARAMETERS_GROUP)

        form = QFormLayout(group)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        self._min_len = QSpinBox()
        self._min_len.setObjectName(names.TRACKING_INSPECTOR_MIN_LEN)
        self._min_len.setRange(2, 1000)
        self._min_len.setValue(5)
        self._min_len.setToolTip(texts.INSPECTOR_TOOLTIP_MIN_LEN)
        self._min_len.valueChanged.connect(self.min_len_changed.emit)

        form.addRow(
            texts.INSPECTOR_LABEL_MIN_LEN,
            self._min_len,
        )

        self._max_gap = QSpinBox()
        self._max_gap.setObjectName(names.TRACKING_INSPECTOR_MAX_GAP)
        self._max_gap.setRange(0, 100)
        self._max_gap.setValue(3)
        self._max_gap.setToolTip(texts.INSPECTOR_TOOLTIP_MAX_GAP)
        self._max_gap.valueChanged.connect(self.max_gap_changed.emit)

        form.addRow(
            texts.INSPECTOR_LABEL_MAX_GAP,
            self._max_gap,
        )

        self._max_speed = QDoubleSpinBox()
        self._max_speed.setObjectName(names.TRACKING_INSPECTOR_MAX_SPEED)
        self._max_speed.setRange(0.01, 10000.0)
        self._max_speed.setDecimals(2)
        self._max_speed.setSingleStep(10.0)
        self._max_speed.setValue(250.0)
        self._max_speed.setToolTip(texts.INSPECTOR_TOOLTIP_MAX_SPEED)
        self._max_speed.valueChanged.connect(self.max_speed_changed.emit)

        form.addRow(
            texts.INSPECTOR_LABEL_MAX_SPEED,
            self._max_speed,
        )

        self._main_layout.addWidget(group)
