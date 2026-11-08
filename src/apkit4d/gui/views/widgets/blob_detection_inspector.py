from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import texts
from apkit4d.gui.constants.application import DEFAULT_PROCESSED_DATA_DIR
from apkit4d.gui.models.output_type import OutputType
from apkit4d.gui.shared.components.v_separator import VSeparator


class BlobDetectionInspector(QWidget):
    """Inspector widget for configuring blob detection parameters and batch processing settings.

    Args:
        parent: Optional parent widget.

    Signals:
        frame_start_changed: Emitted when the start frame changes.
        frame_end_changed: Emitted when the end frame changes.
        output_folder_changed: Emitted when the output folder path changes.
        workers_changed: Emitted when the worker count changes.
        output_format_changed: Emitted when the output format changes.
        diameter_xy_changed: Emitted when the XY diameter changes.
        diameter_z_changed: Emitted when the Z diameter changes.
        diameter_z_equal_to_xy_toggled: Emitted when the Z equals XY toggle state changes.
        lo_g_changed: Emitted when the Laplacian of Gaussian threshold changes.
        seed_separation_changed: Emitted when the seed separation changes.
        boundary_changed: Emitted when the boundary changes.
        min_volume_changed: Emitted when the minimum volume changes.
        max_volume_changed: Emitted when the maximum volume changes.
        update_on_change_toggled: Emitted when the update-on-change toggle state changes.
        show_segments_toggled: Emitted when the show-segments toggle state changes.
        find_blob_clicked: Emitted when the find blobs button is clicked.
    """

    frame_start_changed: Signal = Signal(int)
    frame_end_changed: Signal = Signal(int)
    output_folder_changed: Signal = Signal(Path)
    workers_changed: Signal = Signal(int)
    output_format_changed: Signal = Signal(OutputType)
    diameter_xy_changed: Signal = Signal(float)
    diameter_z_changed: Signal = Signal(float)
    diameter_z_equal_to_xy_toggled: Signal = Signal(bool)
    lo_g_changed: Signal = Signal(float)
    seed_separation_changed: Signal = Signal(float)
    boundary_changed: Signal = Signal(float)
    min_volume_changed: Signal = Signal(float)
    max_volume_changed: Signal = Signal(float)
    update_on_change_toggled: Signal = Signal(bool)
    show_segments_toggled: Signal = Signal(bool)
    find_blob_clicked: Signal = Signal()

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(12)

        self._build_batch_processing_section()
        self._build_detection_parameters_section()

        print(self._output_format.currentData)

    def _create_double_spinbox(
        self,
        value: float,
        minimum: float = 0,
        maximum: float = 1000,
        step: float = 1,
        decimals: int = 2,
    ) -> QDoubleSpinBox:
        spinbox = QDoubleSpinBox()
        spinbox.setRange(minimum, maximum)
        spinbox.setSingleStep(step)
        spinbox.setDecimals(decimals)
        spinbox.setValue(value)
        spinbox.setMinimumWidth(100)
        return spinbox

    def _create_section(self, title: str) -> tuple[QGroupBox, QFormLayout]:
        group = QGroupBox(title)
        layout = QFormLayout(group)
        layout.setSpacing(10)
        layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        return group, layout

    def _build_batch_processing_section(self):
        group, form = self._create_section(texts.INSPECTOR_SECTION_BATCH_PROCESSING)

        # frame selection
        self._frame_start = QSpinBox()
        self._frame_start.setRange(0, 999999)
        self._frame_start.valueChanged.connect(self.frame_start_changed.emit)

        self._frame_end = QSpinBox()
        self._frame_end.setRange(0, 999999)
        self._frame_end.valueChanged.connect(self.frame_end_changed.emit)

        frame_range_widget = QWidget()
        frame_layout = QHBoxLayout(frame_range_widget)
        frame_layout.setContentsMargins(0, 0, 0, 0)
        frame_layout.setSpacing(8)

        frame_layout.addWidget(QLabel(texts.START_TIME_LABEL), alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addWidget(self._frame_start)
        frame_layout.addWidget(QLabel(texts.END_TIME_LABEL), alignment=Qt.AlignmentFlag.AlignRight)
        frame_layout.addWidget(self._frame_end)

        self._frame_range_label = QLabel(texts.INSPECTOR_LABEL_FRAME_RANGE)
        self._frame_range_label.setToolTip(texts.INSPECTOR_TOOLTIP_FRAME_RANGE)
        form.addRow(self._frame_range_label, frame_range_widget)
        form.addRow(VSeparator())

        self._main_layout.addWidget(group)

        self._frame_start.valueChanged.connect(
            lambda v: self._frame_end.setValue(v) if v > self._frame_end.value() else None
        )
        self._frame_end.valueChanged.connect(
            lambda v: self._frame_start.setValue(v) if v < self._frame_start.value() else None
        )

        # batch
        self._output_folder = QLineEdit()
        self._output_folder.setText(str(DEFAULT_PROCESSED_DATA_DIR))
        self._output_folder.setPlaceholderText(texts.INSPECTOR_PLACEHOLDER_OUTPUT_FOLDER)
        self._output_folder.textChanged.connect(lambda path: self.output_folder_changed.emit(Path(path)))

        self.output_browse_button = QPushButton("...")
        self.output_browse_button.setFixedWidth(32)
        self.output_browse_button.clicked.connect(self._choose_output_folder)

        output_widget = QWidget()
        output_layout = QHBoxLayout(output_widget)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.addWidget(self._output_folder)
        output_layout.addWidget(self.output_browse_button)

        form.addRow(texts.INSPECTOR_LABEL_OUTPUT_FOLDER, output_widget)

        self._workers = QSpinBox()
        self._workers.setRange(1, 256)
        self._workers.setValue(4)
        self._workers.valueChanged.connect(self.workers_changed.emit)

        form.addRow(texts.INSPECTOR_LABEL_WORKERS, self._workers)

        self._output_format = QComboBox()
        for item_type in OutputType:
            label = texts.get_output_type_label(item_type)
            self._output_format.addItem(label, item_type)
        self._output_format.currentIndexChanged.connect(
            lambda _: self.output_format_changed.emit(self._output_format.currentData())
        )

        form.addRow(texts.INSPECTOR_LABEL_FORMAT, self._output_format)

        self._main_layout.addWidget(group)

    def _build_detection_parameters_section(self):
        group, form = self._create_section(texts.INSPECTOR_SECTION_DETECTION_PARAMETERS)

        self._diameter_xy = self._create_double_spinbox(2.0, minimum=1, maximum=200)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_DIAMETER_XY,
            self._diameter_xy,
            texts.INSPECTOR_TOOLTIP_DIAMETER_XY,
        )
        self._diameter_xy.valueChanged.connect(self.diameter_xy_changed.emit)

        self._diameter_z = self._create_double_spinbox(5.0, minimum=1, maximum=500)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_DIAMETER_Z,
            self._diameter_z,
            texts.INSPECTOR_TOOLTIP_DIAMETER_Z,
        )
        self._diameter_z.valueChanged.connect(self.diameter_z_changed.emit)

        self._diameter_z_equals_xy = QCheckBox()
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_DIAMETER_Z_EQUALS_XY,
            self._diameter_z_equals_xy,
            texts.INSPECTOR_TOOLTIP_DIAMETER_Z_EQUALS_XY,
        )
        self._diameter_z_equals_xy.toggled.connect(self.diameter_z_equal_to_xy_toggled.emit)

        self._lo_g_threshold = self._create_double_spinbox(0.1, minimum=0, maximum=5, step=0.01)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_LOG_THRESHOLD,
            self._lo_g_threshold,
            texts.INSPECTOR_TOOLTIP_LOG_THRESHOLD,
        )
        self._lo_g_threshold.valueChanged.connect(self.lo_g_changed.emit)

        self._seed_separation = self._create_double_spinbox(0.1, minimum=0.1, maximum=3, step=0.05)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_SEED_SEPARATION,
            self._seed_separation,
            texts.INSPECTOR_TOOLTIP_SEED_SEPARATION,
        )
        self._seed_separation.valueChanged.connect(self.seed_separation_changed.emit)

        self._boundary = self._create_double_spinbox(0.0, minimum=0.01, maximum=0.99, step=0.05)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_BOUNDARY,
            self._boundary,
            texts.INSPECTOR_TOOLTIP_BOUNDARY,
        )
        self._boundary.valueChanged.connect(self.boundary_changed.emit)

        self._min_volume = self._create_double_spinbox(200, maximum=10_000_000, step=100)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_MIN_VOLUME,
            self._min_volume,
            texts.INSPECTOR_TOOLTIP_MIN_VOLUME,
        )
        self._min_volume.valueChanged.connect(self.min_volume_changed.emit)

        self._max_volume = self._create_double_spinbox(1_000_000, maximum=1_000_000_000, step=1000)
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_MAX_VOLUME,
            self._max_volume,
            texts.INSPECTOR_TOOLTIP_MAX_VOLUME,
        )
        self._max_volume.valueChanged.connect(self.max_volume_changed.emit)

        self._main_layout.addWidget(group)

        form.addRow(VSeparator())

        # execution options
        self._update_on_change = QCheckBox()
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_UPDATE_ON_CHANGE,
            self._update_on_change,
            texts.INSPECTOR_TOOLTIP_UPDATE_ON_CHANGE,
        )
        self._update_on_change.toggled.connect(self.update_on_change_toggled.emit)

        self._show_segments = QCheckBox()
        self._add_field(
            form,
            texts.INSPECTOR_LABEL_SHOW_SEGMENTS,
            self._show_segments,
            texts.INSPECTOR_TOOLTIP_SHOW_SEGMENTS,
        )
        self._show_segments.toggled.connect(self.show_segments_toggled.emit)

        self._find_blobs_button = QPushButton(texts.INSPECTOR_BUTTON_FIND_BLOBS)
        self._find_blobs_button.setToolTip(texts.INSPECTOR_TOOLTIP_FIND_BLOBS)
        self._find_blobs_button.clicked.connect(self.find_blob_clicked.emit)

        form.addRow(self._find_blobs_button)

        self._detection_status = QLabel(texts.INSPECTOR_STATUS_NO_BLOBS)
        self._detection_status.setWordWrap(True)

        form.addRow(self._detection_status)

        self._main_layout.addWidget(group)

    def _add_field(
        self,
        form: QFormLayout,
        label_text: str,
        widget: QWidget,
        tooltip: str,
    ):
        label = QLabel(label_text)
        label.setToolTip(tooltip)
        widget.setToolTip(tooltip)
        form.addRow(label, widget)

    def _choose_output_folder(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            texts.INSPECTOR_DIALOG_OUTPUT_FOLDER,
            self._output_folder.text(),
        )

        if directory:
            self._output_folder.setText(directory)

    def set_detection_status(self, status: str):
        """Updates the status text displayed in the blob detection status label.

        Args:
            status: The status message string to display to the user.
        """

        self._detection_status.setText(status)
