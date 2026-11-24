from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QWidget,
)


class MultiFilePanel(QWidget):
    """Show queued recordings, their progress, and the controls for starting a run.

    The controller supplies the rows and status messages. Export settings are
    shared with the Batch Export section of the right panel.
    """

    def __init__(self) -> None:
        super().__init__()
        layout = QFormLayout(self)
        self.recordings = QListWidget()
        layout.addRow(self.recordings)
        self.tracking = QCheckBox("Include tracking")
        self.tracking.setChecked(True)
        self.run = QPushButton("Run")
        self.run.setEnabled(False)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addRow(self.tracking, self.run)
        layout.addRow(self.status)
        layout.addRow(QLabel("Export settings are in step 5, Batch Export."))
