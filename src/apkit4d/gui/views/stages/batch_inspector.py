"""Output and frame controls for batch processing."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from apkit4d.core.frame_range import FrameRange
from apkit4d.gui.constants import names, texts
from apkit4d.gui.views.widgets.frames_selector import FramesSelector
from apkit4d.gui.views.widgets.wheel_guard import install_wheel_guard
from apkit4d.io.table import FORMATS


class BatchInspector(QWidget):
    """Collect output settings; processing and file writing belong to the controller.

    Signals:
        reset_requested: Emitted when the user resets the settings to their defaults.
        selected_frames_confirmed: Emitted with the `FrameRange` to export (or None when there are
            no frames) every time the selection is confirmed or its limits change.
    """

    reset_requested: Signal = Signal()
    selected_frames_confirmed: Signal = Signal(object)  # FrameRange | None

    def __init__(self) -> None:
        super().__init__()
        self._default_output_dir: str = ""
        self._frame_bounds: FrameRange | None = None

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
        self.frames_selector = FramesSelector(None)
        self.frames_selector.setToolTip(texts.BATCH_FRAMES_TOOLTIP)
        self.frames_selector.selected_frames_confirmed.connect(self.selected_frames_confirmed.emit)
        layout.addRow(texts.BATCH_FRAMES, self.frames_selector)

        self.reset_btn = QPushButton(texts.BUTTON_RESET_DEFAULTS)
        self.reset_btn.setObjectName(names.BATCH_INSPECTOR_RESET_BUTTON)
        self.reset_btn.clicked.connect(self._on_reset_clicked)
        layout.addRow(self.reset_btn)

        self.setEnabled(False)
        self._wheel_guard = install_wheel_guard(self)

    @property
    def selected_frames(self) -> FrameRange | None:
        """The frames to export (zero-based, inclusive), or None when there are no frames."""
        return self.frames_selector.selected_frames

    def set_frames_range(self, bounds: FrameRange | None) -> None:
        """Limit the frames that can be selected, and select all of them.

        Args:
            bounds: Frames of the ROI (zero-based, inclusive), or None when there are no frames.
        """

        expand = self._frame_bounds is None
        self._frame_bounds = bounds
        self.frames_selector.set_frame_range(bounds, expand)

    def set_selected_frames(self, start: int, end: int) -> None:
        """Select frames, clamped to the bounds.

        Args:
            start: start frame (1-based)
            end: end frame (1-based)
        """
        self.frames_selector.set_selected_frames(start, end)

    def set_enabled_state(self, enabled: bool) -> None:
        """Enable or disable batch export controls."""
        self.setEnabled(enabled)

    def set_default_output_dir(self, path: str) -> None:
        """Record the default output directory used when resetting batch settings."""
        self._default_output_dir = path

    def reset_to_defaults(self) -> None:
        """Restore output directory, format, and selected frames to defaults."""
        self.output_dir.setText(self._default_output_dir)
        self.format.setCurrentText("parquet")
        self.frames_selector.set_frame_range(self._frame_bounds, True)

    def _on_reset_clicked(self) -> None:
        self.reset_to_defaults()
        self.reset_requested.emit()

    def _choose_directory(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, texts.BATCH_OUTPUT, self.output_dir.text())
        if folder:
            self.output_dir.setText(folder)
