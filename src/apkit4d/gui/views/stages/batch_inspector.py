"""Output and frame controls for batch processing."""

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

from apkit4d.gui.constants import texts
from apkit4d.io.table import FORMATS


class BatchInspector(QWidget):
    """Collect output settings; processing and file writing belong to the controller."""

    def __init__(self) -> None:
        super().__init__()
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
        self.setEnabled(False)

    def set_enabled_state(self, enabled: bool) -> None:
        """Enable or disable batch export controls."""
        self.setEnabled(enabled)

    def _choose_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, texts.BATCH_OUTPUT, self.output_dir.text())
        if folder:
            self.output_dir.setText(folder)
