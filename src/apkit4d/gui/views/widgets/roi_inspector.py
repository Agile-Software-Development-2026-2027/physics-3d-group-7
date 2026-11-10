"""Inspector widget for selecting and editing the 3D Region of Interest"""

from PySide6.QtCore import QSignalBlocker, Qt, Signal
from PySide6.QtWidgets import (
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.gui.shared.components.v_separator import VSeparator
from apkit4d.roi import Bounds6D, RegionOfInterest


class RoiInspector(QWidget):
    """
    Inspector widget for configuring the 3D Region of Interest (ROI) via keyboard
    spinboxes or interactive 3D viewport selection.

    Signals:
        select_roi_clicked: Emitted when the user clicks 'Select ROI on 3D View'.
        accept_roi_clicked: Emitted when the user confirms the ROI preview.
        cancel_roi_clicked: Emitted when the user cancels the ROI selection/preview.
        reset_roi_clicked: Emitted when the user resets the ROI to the full volume.
        bounds_edited: Emitted with a `RegionOfInterest` when spinboxes are edited manually.
    """

    select_roi_clicked = Signal()
    accept_roi_clicked = Signal()
    cancel_roi_clicked = Signal()
    reset_roi_clicked = Signal()
    bounds_edited = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._volume_bounds: Bounds6D | None = None

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(12)

        self._build_roi_section()
        self.set_editing_mode(False)

    # helper to create the 6 spinboxes for X/Y/Z min/max coordinates in micrometers
    def _create_spinbox(self, object_name: str) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setObjectName(object_name)
        spinbox.setRange(0.0, 100_000.0)
        spinbox.setSingleStep(1.0)
        spinbox.setDecimals(2)
        spinbox.setMinimumWidth(75)
        spinbox.valueChanged.connect(self._on_spinbox_value_changed)
        return spinbox

    # helper to create a row with min/max spinboxes for one axis
    def _create_axis_row(self, min_spin: QDoubleSpinBox, max_spin: QDoubleSpinBox) -> QWidget:
        row_widget = QWidget()
        layout = QHBoxLayout(row_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(QLabel(texts.ROI_MIN_LABEL), alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(min_spin)
        layout.addWidget(QLabel(texts.ROI_MAX_LABEL), alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(max_spin)
        return row_widget

    # Build the ROI section of the inspector with spinboxes, buttons, and status label
    def _build_roi_section(self) -> None:
        group = QGroupBox(texts.INSPECTOR_SECTION_ROI_BOUNDS)
        group.setObjectName(names.ROI_INSPECTOR_BOUNDS_GROUP)
        form = QFormLayout(group)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        # X, Y, Z min/max spinboxes in micrometers
        self._x_min = self._create_spinbox(names.ROI_INSPECTOR_X_MIN)
        self._x_max = self._create_spinbox(names.ROI_INSPECTOR_X_MAX)
        self._y_min = self._create_spinbox(names.ROI_INSPECTOR_Y_MIN)
        self._y_max = self._create_spinbox(names.ROI_INSPECTOR_Y_MAX)
        self._z_min = self._create_spinbox(names.ROI_INSPECTOR_Z_MIN)
        self._z_max = self._create_spinbox(names.ROI_INSPECTOR_Z_MAX)

        form.addRow(texts.INSPECTOR_LABEL_ROI_X, self._create_axis_row(self._x_min, self._x_max))
        form.addRow(texts.INSPECTOR_LABEL_ROI_Y, self._create_axis_row(self._y_min, self._y_max))
        form.addRow(texts.INSPECTOR_LABEL_ROI_Z, self._create_axis_row(self._z_min, self._z_max))
        form.addRow(VSeparator())

        # Interactive 3D selection button
        self._select_btn = QPushButton(texts.INSPECTOR_BUTTON_SELECT_ROI)
        self._select_btn.setObjectName(names.ROI_INSPECTOR_SELECT_BUTTON)
        self._select_btn.setToolTip(texts.INSPECTOR_TOOLTIP_SELECT_ROI)
        self._select_btn.clicked.connect(self.select_roi_clicked.emit)
        form.addRow(self._select_btn)

        # Accept and cancel buttons side by side
        action_widget = QWidget()
        action_layout = QHBoxLayout(action_widget)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.setSpacing(8)

        self._accept_btn = QPushButton(texts.INSPECTOR_BUTTON_ACCEPT_ROI)
        self._accept_btn.setObjectName(names.ROI_INSPECTOR_ACCEPT_BUTTON)
        self._accept_btn.setToolTip(texts.INSPECTOR_TOOLTIP_ACCEPT_ROI)
        self._accept_btn.clicked.connect(self.accept_roi_clicked.emit)

        self._cancel_btn = QPushButton(texts.INSPECTOR_BUTTON_CANCEL_ROI)
        self._cancel_btn.setObjectName(names.ROI_INSPECTOR_CANCEL_BUTTON)
        self._cancel_btn.setToolTip(texts.INSPECTOR_TOOLTIP_CANCEL_ROI)
        self._cancel_btn.clicked.connect(self.cancel_roi_clicked.emit)

        action_layout.addWidget(self._accept_btn)
        action_layout.addWidget(self._cancel_btn)
        form.addRow(action_widget)

        # Reset to full volume button
        self._reset_btn = QPushButton(texts.INSPECTOR_BUTTON_RESET_ROI)
        self._reset_btn.setObjectName(names.ROI_INSPECTOR_RESET_BUTTON)
        self._reset_btn.setToolTip(texts.INSPECTOR_TOOLTIP_RESET_ROI)
        self._reset_btn.clicked.connect(self.reset_roi_clicked.emit)
        form.addRow(self._reset_btn)

        # Status label
        self._status_label = QLabel(texts.INSPECTOR_STATUS_ROI_FULL)
        self._status_label.setObjectName(names.ROI_INSPECTOR_STATUS_LABEL)
        self._status_label.setWordWrap(True)
        form.addRow(self._status_label)

        self._main_layout.addWidget(group)

    def set_volume_bounds(self, bounds: Bounds6D) -> None:
        """
        Configure the min/max range of all spinboxes to match the loaded 3D volume bounds
        and initialize the spinbox values to the full volume.
        """
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

        self.set_roi_bounds(bounds)

    def set_roi_bounds(self, bounds: Bounds6D) -> None:
        """
        Update the 6 spinboxes to show `bounds` without triggering `bounds_edited`.
        Called when the user drags the mouse or handles in the 3D Viewport.

        Parameters:
            bounds: A 6-tuple of (x_min, x_max, y_min, y_max, z_min, z_max) in micrometers.

        Returns:
            None
        """
        x0, x1, y0, y1, z0, z1 = bounds
        for spin, val in (
            (self._x_min, x0),
            (self._x_max, x1),
            (self._y_min, y0),
            (self._y_max, y1),
            (self._z_min, z0),
            (self._z_max, z1),
        ):
            # Block signals temporarily to avoid triggering the valueChanged
            # signal when updating the spinbox values
            with QSignalBlocker(spin):
                spin.setValue(val)

    def get_roi(self) -> RegionOfInterest:
        """Return `RegionOfInterest` built from the current spinbox values"""
        raw: Bounds6D = (
            self._x_min.value(),
            self._x_max.value(),
            self._y_min.value(),
            self._y_max.value(),
            self._z_min.value(),
            self._z_max.value(),
        )
        return RegionOfInterest.from_bounds(raw, volume_bounds=self._volume_bounds)

    def set_editing_mode(self, editing: bool) -> None:
        """Enable or disable the Accept and Cancel buttons based on whether a preview is active."""
        self._accept_btn.setEnabled(editing)
        self._cancel_btn.setEnabled(editing)
        if editing:
            self._status_label.setText(texts.INSPECTOR_STATUS_ROI_SELECTING)

    def set_status_text(self, text: str) -> None:
        """Update the ROI status label text."""
        self._status_label.setText(text)

    def _on_spinbox_value_changed(self) -> None:
        """
        Called when the user manually edits any of the 6 coordinate spinboxes.
        Keeps min <= max, switches to editing mode, and emits `bounds_edited`
        so the 3D Viewport preview box updates immediately.
        """
        roi = self.get_roi()
        self.set_roi_bounds(roi.bounds)
        self.set_editing_mode(True)
        self.bounds_edited.emit(roi)
