"""Collapsible Visualization Sub-ROI section for the left panel."""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from apkit4d.core.roi import Bounds6D
from apkit4d.gui.constants import names, texts, view_style
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, ThemeColors
from apkit4d.gui.views.widgets.accordion import AccordionSection
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.gui.views.widgets.v_separator import VSeparator
from apkit4d.visualization.vis_sub_roi import VisSubRoiState, clamp_outside_opacity


class VisSubRoiSection(AccordionSection):
    """Accordion section hosting Visualization Sub-ROI controls in the left panel.

    This widget holds no controller or pipeline logic: it emits user actions via
    signals and accepts programmatic state updates without feedback loops.

    Signals:
        enabled_toggled: Emitted when the enable/disable checkbox changes.
        select_region_clicked: Emitted when 'Select Region in Viewport' is pressed.
        bounds_edited: Emitted with a normalized `Bounds6D` tuple when spinboxes are edited.
        outside_opacity_changed: Emitted with a float opacity multiplier in `[0.0, 1.0]`.
        reset_clicked: Emitted when 'Reset Sub-ROI' is pressed.
    """

    enabled_toggled = Signal(bool)
    select_region_clicked = Signal()
    bounds_edited = Signal(object)
    outside_opacity_changed = Signal(float)
    reset_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(texts.SECTION_VIS_SUB_ROI, parent=parent)
        self.setObjectName(names.VIS_SUB_ROI_SECTION)

        self._volume_bounds: Bounds6D | None = None
        self._available: bool = False

        # enable/disable checkbox and select button
        self._enabled_checkbox = QCheckBox(texts.LABEL_VIS_SUB_ROI_ENABLE)
        self._enabled_checkbox.setObjectName(names.VIS_SUB_ROI_ENABLED_CHECKBOX)
        self._enabled_checkbox.setChecked(False)
        self._enabled_checkbox.toggled.connect(self.enabled_toggled)

        self._select_button = QPushButton(texts.BUTTON_VIS_SUB_ROI_SELECT)
        self._select_button.setObjectName(names.VIS_SUB_ROI_SELECT_BUTTON)
        self._select_button.setToolTip(texts.TOOLTIP_VIS_SUB_ROI_SELECT)
        self._select_button.clicked.connect(self.select_region_clicked)

        # spinboxes for the 6D bounds
        self._x_min = self._create_spinbox(names.VIS_SUB_ROI_X_MIN)
        self._x_max = self._create_spinbox(names.VIS_SUB_ROI_X_MAX)
        self._y_min = self._create_spinbox(names.VIS_SUB_ROI_Y_MIN)
        self._y_max = self._create_spinbox(names.VIS_SUB_ROI_Y_MAX)
        self._z_min = self._create_spinbox(names.VIS_SUB_ROI_Z_MIN)
        self._z_max = self._create_spinbox(names.VIS_SUB_ROI_Z_MAX)

        # layout for the 6D bounds spinboxes
        bounds_widget = QWidget()
        bounds_form = QFormLayout(bounds_widget)
        bounds_form.setContentsMargins(0, 0, 0, 0)
        bounds_form.setSpacing(6)
        bounds_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        bounds_form.addRow(texts.LABEL_VIS_SUB_ROI_X, self._create_axis_row(self._x_min, self._x_max))
        bounds_form.addRow(texts.LABEL_VIS_SUB_ROI_Y, self._create_axis_row(self._y_min, self._y_max))
        bounds_form.addRow(texts.LABEL_VIS_SUB_ROI_Z, self._create_axis_row(self._z_min, self._z_max))

        # outside opacity slider and value label
        self._outside_opacity_slider = FrameSlider(preview=False)
        self._outside_opacity_slider.setObjectName(names.VIS_SUB_ROI_OPACITY_SLIDER)
        self._outside_opacity_slider.setRange(
            view_style.VIS_SUB_ROI_OPACITY_MIN_PERCENT,
            view_style.VIS_SUB_ROI_OPACITY_MAX_PERCENT,
        )
        self._outside_opacity_slider.setValue(view_style.VIS_SUB_ROI_OPACITY_DEFAULT_PERCENT)
        self._outside_opacity_slider.valueChanged.connect(self._on_outside_opacity_moved)

        self._outside_opacity_value = QLabel(
            texts.OPACITY_VALUE.format(percent=view_style.VIS_SUB_ROI_OPACITY_DEFAULT_PERCENT)
        )
        self._outside_opacity_value.setObjectName(names.VIS_SUB_ROI_OPACITY_VALUE)
        self._outside_opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        widest = texts.OPACITY_VALUE.format(percent=view_style.VIS_SUB_ROI_OPACITY_MAX_PERCENT)
        self._outside_opacity_value.setMinimumWidth(
            self._outside_opacity_value.fontMetrics().horizontalAdvance(widest)
        )

        # layout for the outside opacity slider and value label
        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.addWidget(self._outside_opacity_slider)
        opacity_layout.addWidget(self._outside_opacity_value)

        self._opacity_box = QWidget()
        self._opacity_box.setObjectName(names.VIS_SUB_ROI_OPACITY_BOX)
        opacity_box_layout = QHBoxLayout(self._opacity_box)
        opacity_box_layout.setSpacing(5)
        opacity_box_layout.addWidget(QLabel(texts.BOX_VIS_SUB_ROI_OUTSIDE_OPACITY))
        opacity_box_layout.addWidget(opacity_row)

        # reset button and status label
        self._reset_button = QPushButton(texts.BUTTON_VIS_SUB_ROI_RESET)
        self._reset_button.setObjectName(names.VIS_SUB_ROI_RESET_BUTTON)
        self._reset_button.setToolTip(texts.TOOLTIP_VIS_SUB_ROI_RESET)
        self._reset_button.clicked.connect(self.reset_clicked)

        self._status_label = QLabel(texts.STATUS_VIS_SUB_ROI_UNAVAILABLE)
        self._status_label.setObjectName(names.VIS_SUB_ROI_STATUS_LABEL)
        self._status_label.setWordWrap(True)

        # add all widgets to the section layout (accordion)
        self.add_widget(self._enabled_checkbox)
        self.add_widget(self._select_button)
        self.add_widget(VSeparator())
        self.add_widget(bounds_widget)
        self.add_widget(VSeparator())
        self.add_widget(self._opacity_box)
        self.add_widget(self._reset_button)
        self.add_widget(self._status_label)

        # keep track of the controls that must be enabled or disabled together.
        # the status label remains available to explain the current state.
        self._interactive_controls: tuple[QWidget, ...] = (
            self._enabled_checkbox,
            self._select_button,
            self._x_min,
            self._x_max,
            self._y_min,
            self._y_max,
            self._z_min,
            self._z_max,
            self._outside_opacity_slider,
            self._reset_button,
        )

        self.set_available(False)
        self.apply_theme(THEME_COLORS[DEFAULT_THEME])

    def _create_spinbox(self, object_name: str) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setObjectName(object_name)
        spinbox.setRange(-100_000.0, 100_000.0)
        spinbox.setSingleStep(1.0)
        spinbox.setDecimals(2)
        spinbox.setMinimumWidth(68)
        spinbox.valueChanged.connect(self._on_spinbox_value_changed)
        return spinbox

    @staticmethod
    def _create_axis_row(min_spin: QDoubleSpinBox, max_spin: QDoubleSpinBox) -> QWidget:
        row_widget = QWidget()
        layout = QHBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(QLabel(texts.LABEL_VIS_SUB_ROI_MIN), alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(min_spin)
        layout.addWidget(QLabel(texts.LABEL_VIS_SUB_ROI_MAX), alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(max_spin)
        return row_widget

    @property
    def is_available(self) -> bool:
        """Whether interactive Visualization Sub-ROI controls are currently unlocked."""
        return self._available

    @property
    def is_sub_roi_enabled(self) -> bool:
        """Whether the enable checkbox is currently checked."""
        return self._enabled_checkbox.isChecked()

    @property
    def outside_opacity(self) -> float:
        """Configured outside opacity multiplier in `[0.0, 1.0]`."""
        return self._outside_opacity_slider.value() / 100.0

    @property
    def bounds(self) -> Bounds6D:
        """Current `(x_min, x_max, y_min, y_max, z_min, z_max)` shown in the spinboxes."""
        return (
            self._x_min.value(),
            self._x_max.value(),
            self._y_min.value(),
            self._y_max.value(),
            self._z_min.value(),
            self._z_max.value(),
        )

    # Setters and some helper methods to update the state of controls

    def set_available(self, available: bool) -> None:
        """Enable or disable inner interactive controls while keeping the section header usable."""
        self._available = bool(available)
        for control in self._interactive_controls:
            control.setEnabled(self._available)
        if not self._available:
            self._status_label.setText(texts.STATUS_VIS_SUB_ROI_UNAVAILABLE)
        elif self._status_label.text() == texts.STATUS_VIS_SUB_ROI_UNAVAILABLE:
            self._status_label.setText(texts.STATUS_VIS_SUB_ROI_INACTIVE)

    def set_volume_bounds(self, bounds: Bounds6D) -> None:
        """Configure spinbox ranges to match the active volume bounds without emitting signals."""
        self._volume_bounds = bounds
        x0, x1, y0, y1, z0, z1 = bounds
        for spin, lo, hi in (
            (self._x_min, x0, x1),
            (self._x_max, x0, x1),
            (self._y_min, y0, y1),
            (self._y_max, y0, y1),
            (self._z_min, z0, z1),
            (self._z_max, z0, z1),
        ):
            with QSignalBlocker(spin):
                spin.setRange(lo, hi)
        self.set_sub_roi_bounds(bounds)

    def set_sub_roi_bounds(self, bounds: Bounds6D | None) -> None:
        """Programmatically display `bounds` in the 6 spinboxes without emitting `bounds_edited`."""
        target = bounds if bounds is not None else self._volume_bounds
        if target is None:
            return
        x0, x1, y0, y1, z0, z1 = target
        for spin, val in (
            (self._x_min, x0),
            (self._x_max, x1),
            (self._y_min, y0),
            (self._y_max, y1),
            (self._z_min, z0),
            (self._z_max, z1),
        ):
            with QSignalBlocker(spin):
                spin.setValue(val)

    def set_sub_roi_enabled(self, enabled: bool) -> None:
        """Programmatically update the enable checkbox without emitting `enabled_toggled`."""
        with QSignalBlocker(self._enabled_checkbox):
            self._enabled_checkbox.setChecked(bool(enabled))

    def set_outside_opacity(self, opacity: float) -> None:
        """Programmatically update outside opacity (`0.0..1.0`) without emitting a signal."""
        clamped = clamp_outside_opacity(opacity)
        percent = int(round(clamped * 100.0))
        with QSignalBlocker(self._outside_opacity_slider):
            self._outside_opacity_slider.setValue(percent)
        self._outside_opacity_value.setText(texts.OPACITY_VALUE.format(percent=percent))

    def set_state(self, state: VisSubRoiState) -> None:
        """Synchronize all controls from a `VisSubRoiState` without emitting signals."""
        self.set_sub_roi_enabled(state.enabled)
        self.set_sub_roi_bounds(state.bounds)
        self.set_outside_opacity(state.outside_opacity)

    def set_status_text(self, text: str) -> None:
        """Update the section status text."""
        self._status_label.setText(text)

    def apply_theme(self, colors: ThemeColors) -> None:
        """Apply active theme colors to the accordion header and content area."""
        super().apply_theme(colors)

    def _on_outside_opacity_moved(self, percent: int) -> None:
        self._outside_opacity_value.setText(texts.OPACITY_VALUE.format(percent=percent))
        self.outside_opacity_changed.emit(percent / 100.0)

    def _on_spinbox_value_changed(self) -> None:
        state = VisSubRoiState(
            enabled=self.is_sub_roi_enabled,
            bounds=self.bounds,
            outside_opacity=self.outside_opacity,
        ).with_clamped_bounds(self._volume_bounds)
        assert state.bounds is not None
        self.set_sub_roi_bounds(state.bounds)
        self.bounds_edited.emit(state.bounds)
