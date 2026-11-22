"""Output and frame controls for batch processing."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.io.table import FORMATS


class BatchInspector(QWidget):
    """Collect output settings; processing and file writing belong to the controller."""

    reset_requested: Signal = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._default_output_dir: str = ""

        layout = QFormLayout(self)
        self.output_dir = QLineEdit()
        self.output_dir.setToolTip(texts.BATCH_READY)
        self.browse = QPushButton(texts.BATCH_BROWSE)
        self.browse.clicked.connect(self._choose_directory)
        directory = QHBoxLayout()
        directory.addWidget(self.output_dir)
        directory.addWidget(self.browse)
        layout.addRow(texts.BATCH_OUTPUT, directory)
        self.format = QComboBox()
        self.format.addItems(FORMATS)
        self.format.setCurrentText("parquet")
        layout.addRow(texts.BATCH_FORMAT, self.format)
        self.first_frame = QSpinBox()
        self.last_frame = QSpinBox()
        layout.addRow(texts.BATCH_FIRST_FRAME, self.first_frame)
        layout.addRow(texts.BATCH_LAST_FRAME, self.last_frame)

        self.reset_btn = QPushButton(texts.BUTTON_RESET_DEFAULTS)
        self.reset_btn.setObjectName(names.BATCH_INSPECTOR_RESET_BUTTON)
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        layout.addRow(self.reset_btn)

        self.setEnabled(False)

    def set_enabled_state(self, enabled: bool) -> None:
        """Enable or disable batch export controls."""
        self.setEnabled(enabled)

    def set_default_output_dir(self, path: str) -> None:
        """Record the default output directory used when resetting batch settings."""
        self._default_output_dir = path

    def reset_to_defaults(self) -> None:
        """Restore output directory, format, and frame bounds to defaults."""
        self.output_dir.setText(self._default_output_dir)
        self.format.setCurrentText("parquet")
        self.first_frame.setValue(self.first_frame.minimum())
        self.last_frame.setValue(self.last_frame.maximum())

    def _on_reset_clicked(self) -> None:
        self.reset_to_defaults()
        self.reset_requested.emit()

    def _choose_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, texts.BATCH_OUTPUT, self.output_dir.text())
        if folder:
            self.output_dir.setText(folder)
