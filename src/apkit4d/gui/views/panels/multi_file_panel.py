from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QWidget,
)

from apkit4d.gui.constants import texts


class MultiFilePanel(QWidget):
    """Show queued recordings, their progress, and the controls for starting a run.

    The controller supplies the rows and status messages. Export settings are
    shared with the Batch Export section of the right panel.
    """

    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.recordings = QListWidget()
        self.recordings.setToolTip(texts.MULTI_FILE_REORDER_HINT)
        layout.addRow(self.recordings)
        self.remove = QPushButton(texts.MULTI_FILE_REMOVE)
        self.remove.setEnabled(False)
        layout.addRow(self.remove)
        layout.setAlignment(self.remove, Qt.AlignmentFlag.AlignLeft)
        self.tracking = QCheckBox(texts.MULTI_FILE_TRACKING)
        self.tracking.setChecked(True)
        self.run = QPushButton(texts.MULTI_FILE_RUN)
        self.run.setEnabled(False)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addRow(self.tracking, self.run)
        layout.addRow(self.status)
        layout.addRow(QLabel(texts.MULTI_FILE_EXPORT_HINT))
