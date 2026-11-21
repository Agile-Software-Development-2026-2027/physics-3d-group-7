"""Dialog for exporting viewport frames to a compressed video file."""

from enum import StrEnum
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.video_export_controller import VideoExportController
from apkit4d.gui.views.widgets.frame_slider import FrameSlider


class _VideoPreset(StrEnum):
    """Values of the `-preset` flag we pass to ffmpeg.

    Slower -> better quality.

    Cfr. <https://trac.ffmpeg.org/wiki/Encode/H.264>
    """

    ULTRAFAST = "ultrafast"
    SUPERFAST = "superfast"
    VERYFAST = "veryfast"
    FASTER = "faster"
    FAST = "fast"
    MEDIUM = "medium"
    SLOW = "slow"
    SLOWER = "slower"
    VERYSLOW = "veryslow"


class VideoExportDialog(QDialog):
    """Modal dialog for configuring and running a video export.

    Args:
        controller: The VideoExportController that owns the export logic.
        parent: Optional Qt parent widget.
    """

    def __init__(
        self,
        controller: VideoExportController,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._controller = controller
        self.setObjectName(names.VIDEO_EXPORT_DIALOG)
        self.setWindowTitle(texts.EXPORT_DIALOG_TITLE)
        self.setMinimumWidth(500)

        layout = QVBoxLayout(self)

        layout.addWidget(self._build_preview_group())
        layout.addWidget(self._build_range_group())
        layout.addWidget(self._build_video_settings_group())
        layout.addWidget(self._build_output_group())
        layout.addWidget(self._build_progress_section())
        layout.addLayout(self._build_buttons())

        self._sync_from_controller()
        self._connect_controller_signals()
        self._connect_widget_signals()
        self._request_initial_preview()

    def _build_preview_group(self) -> QGroupBox:
        """Build the preview area showing viewport frame screenshots."""
        group = QGroupBox(texts.EXPORT_LABEL_PREVIEW)
        layout = QVBoxLayout(group)

        self._preview_label = QLabel()
        self._preview_label.setObjectName(names.VIDEO_EXPORT_PREVIEW)
        self._preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview_label.setFrameShape(QFrame.Shape.Box)  # draw the outline of the preview
        self._preview_label.setFrameShadow(QFrame.Shadow.Plain)
        self._preview_label.setLineWidth(1)
        layout.addWidget(self._preview_label, alignment=Qt.AlignmentFlag.AlignCenter)
        return group

    def _build_range_group(self) -> QGroupBox:
        group = QGroupBox("Frame Range")
        layout = QHBoxLayout(group)

        first_frame_row = QHBoxLayout()
        first_frame_row.addStretch()
        first_frame_row.addWidget(QLabel(texts.EXPORT_LABEL_FIRST_FRAME))
        self._first_frame_spin = QSpinBox()
        self._first_frame_spin.setObjectName(names.VIDEO_EXPORT_FIRST_FRAME)
        first_frame_row.addWidget(self._first_frame_spin)
        first_frame_row.addStretch()
        layout.addLayout(first_frame_row, stretch=1)

        last_frame_row = QHBoxLayout()
        last_frame_row.addStretch()
        last_frame_row.addWidget(QLabel(texts.EXPORT_LABEL_LAST_FRAME))
        self._last_frame_spin = QSpinBox()
        self._last_frame_spin.setObjectName(names.VIDEO_EXPORT_LAST_FRAME)
        last_frame_row.addWidget(self._last_frame_spin)
        last_frame_row.addStretch()
        layout.addLayout(last_frame_row, stretch=1)

        return group

    def _build_video_settings_group(self) -> QGroupBox:
        group = QGroupBox(texts.EXPORT_LABEL_VIDEO_SETTINGS)
        layout = QVBoxLayout(group)

        crf_slider_row = QHBoxLayout()
        crf_slider_row.addWidget(QLabel(texts.EXPORT_CRF_HIGH_QUALITY))
        self._crf_slider = FrameSlider(preview=False)
        self._crf_slider.setObjectName(names.VIDEO_EXPORT_CRF_SLIDER)
        self._crf_slider.setRange(0, 51)
        crf_slider_row.addWidget(self._crf_slider)
        crf_slider_row.addWidget(QLabel(texts.EXPORT_CRF_SMALLER_FILE))

        self._crf_value_label = QLabel()
        self._crf_value_label.setObjectName(names.VIDEO_EXPORT_CRF_VALUE)
        self._crf_value_label.setFixedWidth(30)
        self._crf_value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        crf_slider_row.addWidget(self._crf_value_label)

        layout.addLayout(crf_slider_row)

        fps_row = QHBoxLayout()
        fps_row.addWidget(QLabel(texts.EXPORT_LABEL_FPS))
        self._fps_spin = QSpinBox()
        self._fps_spin.setObjectName(names.VIDEO_EXPORT_FPS)
        self._fps_spin.setRange(1, 120)
        fps_row.addWidget(self._fps_spin)
        fps_row.addStretch()
        layout.addLayout(fps_row)

        resolution_row = QHBoxLayout()
        resolution_row.addWidget(QLabel("Resolution (px)"))
        self._width_spin = QSpinBox()
        self._width_spin.setObjectName(names.VIDEO_EXPORT_WIDTH)
        self._width_spin.setRange(1, 8192)
        resolution_row.addWidget(self._width_spin)

        resolution_row.addWidget(QLabel("×"))
        self._height_spin = QSpinBox()
        self._height_spin.setObjectName(names.VIDEO_EXPORT_HEIGHT)
        self._height_spin.setRange(1, 8192)
        resolution_row.addWidget(self._height_spin)
        resolution_row.addStretch()
        layout.addLayout(resolution_row)

        preset_row = QHBoxLayout()
        preset_row.addWidget(QLabel(texts.EXPORT_LABEL_PRESET))
        self._preset_combo = QComboBox()
        self._preset_combo.setObjectName(names.VIDEO_EXPORT_PRESET)
        self._preset_combo.addItems([preset.value for preset in _VideoPreset])
        self._preset_combo.setToolTip(texts.EXPORT_PRESET_TOOLTIP)
        preset_row.addWidget(self._preset_combo)
        preset_row.addStretch()
        layout.addLayout(preset_row)

        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox(texts.EXPORT_LABEL_OUTPUT)
        layout = QHBoxLayout(group)

        layout.addWidget(QLabel(texts.EXPORT_LABEL_OUTPUT_PATH))

        self._output_path_label = QLabel()
        self._output_path_label.setObjectName(names.VIDEO_EXPORT_OUTPUT_PATH)
        self._output_path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._output_path_label, stretch=1)

        self._browse_button = QPushButton(texts.EXPORT_BUTTON_BROWSE)
        self._browse_button.setObjectName(names.VIDEO_EXPORT_BROWSE_BUTTON)
        layout.addWidget(self._browse_button)

        return group

    def _build_progress_section(self) -> QWidget:
        """Build progress bar and status label."""
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)

        self._progress_bar = QProgressBar()
        self._progress_bar.setObjectName(names.VIDEO_EXPORT_PROGRESS_BAR)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        self._status_label = QLabel(texts.EXPORT_STATUS_READY)
        self._status_label.setObjectName(names.VIDEO_EXPORT_STATUS_LABEL)
        layout.addWidget(self._status_label)

        return container

    def _build_buttons(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.addStretch()

        self._export_button = QPushButton(texts.EXPORT_BUTTON_EXPORT)
        self._export_button.setObjectName(names.VIDEO_EXPORT_EXPORT_BUTTON)
        layout.addWidget(self._export_button)

        self._cancel_button = QPushButton(texts.EXPORT_BUTTON_CANCEL)
        self._cancel_button.setObjectName(names.VIDEO_EXPORT_CANCEL_BUTTON)
        layout.addWidget(self._cancel_button)

        return layout

    def _sync_from_controller(self) -> None:
        """Pull the current controller state into every widget."""

        max_frame = max(1, self._controller.total_frames)

        self._first_frame_spin.setRange(1, max_frame)
        self._first_frame_spin.setValue(self._controller.first_frame + 1)

        self._last_frame_spin.setRange(1, max_frame)
        self._last_frame_spin.setValue(self._controller.last_frame + 1)

        self._crf_slider.setValue(self._controller.crf)
        self._crf_value_label.setText(str(self._controller.crf))

        self._fps_spin.setValue(self._controller.fps)
        width, height = self._controller.resolution
        self._width_spin.setValue(width)
        self._height_spin.setValue(height)
        self._preset_combo.setCurrentText(self._controller.preset)

        path = self._controller.output_path
        self._output_path_label.setText(str(path) if path is not None else "")
        self._update_export_button_state()

    def _connect_controller_signals(self) -> None:
        """Connects controller signals (controller -> dialog)"""

        self._controller.export_started.connect(self._on_export_started)
        self._controller.progress_changed.connect(self._on_progress_changed)
        self._controller.export_succeeded.connect(self._on_export_succeeded)
        self._controller.export_failed.connect(self._on_export_failed)
        self._controller.export_cancelled.connect(self._on_export_cancelled)
        self._controller.preview_ready.connect(self._on_preview_ready)
        self._controller.config_changed.connect(self._on_config_changed)

    def _connect_widget_signals(self) -> None:
        """Connect widget signals to controller setters."""

        self._first_frame_spin.valueChanged.connect(self._on_first_frame_changed)
        self._last_frame_spin.valueChanged.connect(self._on_last_frame_changed)
        self._crf_slider.valueChanged.connect(self._on_crf_changed)
        self._fps_spin.valueChanged.connect(self._on_fps_changed)
        self._width_spin.valueChanged.connect(self._on_resolution_changed)
        self._height_spin.valueChanged.connect(self._on_resolution_changed)
        self._preset_combo.currentTextChanged.connect(self._controller.set_preset)
        self._browse_button.clicked.connect(self._on_browse)
        self._export_button.clicked.connect(self._on_export)
        self._cancel_button.clicked.connect(self._on_cancel)

    def _request_initial_preview(self) -> None:
        """Request a preview of the first frame on dialog open."""
        if self._controller.total_frames > 0:
            self._controller.request_preview_frame(self._controller.first_frame)

    def _on_first_frame_changed(self, value: int) -> None:
        frame = value - 1
        self._controller.set_first_frame(frame)
        if self._controller.total_frames > 0:
            self._controller.request_preview_frame(frame)

    def _on_last_frame_changed(self, value: int) -> None:
        self._controller.set_last_frame(value - 1)

    def _on_crf_changed(self, value: int) -> None:
        self._controller.set_crf(value)
        self._crf_value_label.setText(str(value))

    def _on_fps_changed(self, value: int) -> None:
        self._controller.set_fps(value)

    def _on_resolution_changed(self, _: int) -> None:
        self._controller.set_resolution(self._width_spin.value(), self._height_spin.value())
        if self._controller.total_frames > 0:
            self._controller.request_preview_frame(self._controller.first_frame)

    def _on_browse(self) -> None:
        current = self._controller.output_path
        start_dir = str(current.parent) if current is not None else ""
        path, _ = QFileDialog.getSaveFileName(
            self,
            texts.EXPORT_FILE_DIALOG_TITLE,
            start_dir,
            texts.EXPORT_FILE_FILTER,
        )
        if path:
            self._controller.set_output_path(Path(path))
            self._output_path_label.setText(path)
            self._update_export_button_state()

    def _on_export(self) -> None:
        self._controller.start_export()

    def _on_cancel(self) -> None:
        if self._controller.is_exporting:
            self._controller.cancel_export()
        else:
            self.reject()  # closes the dialog. Dialog not destroyed, remains in memory

    def _on_export_started(self) -> None:
        self._progress_bar.setVisible(True)
        self._progress_bar.setValue(0)
        self._status_label.setText(
            texts.EXPORT_STATUS_EXPORTING.format(done=0, total=self._controller.export_frame_count)
        )
        self._set_controls_enabled(False)

    def _on_progress_changed(self, done: int, total: int) -> None:
        self._progress_bar.setMaximum(total)
        self._progress_bar.setValue(done)
        self._status_label.setText(texts.EXPORT_STATUS_EXPORTING.format(done=done, total=total))

    def _on_export_succeeded(self, path: Path) -> None:
        self._set_controls_enabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText(texts.EXPORT_STATUS_DONE.format(path=path.name))

    def _on_export_failed(self, reason: str) -> None:
        self._set_controls_enabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText(texts.EXPORT_STATUS_FAILED.format(reason=reason))

    def _on_export_cancelled(self) -> None:
        self._set_controls_enabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText(texts.EXPORT_STATUS_CANCELLED)

    def _on_preview_ready(self, _frame: int, arr: object) -> None:
        """Displays a frame preview from the controller."""

        if not isinstance(arr, np.ndarray):
            return

        h, w = arr.shape[:2]
        bytes_per_line = 3 * w  # three channels RGB
        qimg = QImage(arr.data, w, h, bytes_per_line, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(qimg).scaled(
            480,
            270,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._preview_label.setPixmap(pixmap)

    def _on_config_changed(self) -> None:
        """Updates the allowed ranges fo the spin boxes after the controller changed"""

        max_frame = max(1, self._controller.total_frames)
        self._first_frame_spin.setRange(1, max_frame)
        self._last_frame_spin.setRange(1, max_frame)
        self._first_frame_spin.setValue(self._controller.first_frame + 1)
        self._last_frame_spin.setValue(self._controller.last_frame + 1)
        self._update_export_button_state()

    def _set_controls_enabled(self, enabled: bool) -> None:
        """Enables or disables all input controls."""

        self._first_frame_spin.setEnabled(enabled)
        self._last_frame_spin.setEnabled(enabled)
        self._crf_slider.setEnabled(enabled)
        self._fps_spin.setEnabled(enabled)
        self._width_spin.setEnabled(enabled)
        self._height_spin.setEnabled(enabled)
        self._preset_combo.setEnabled(enabled)
        self._browse_button.setEnabled(enabled)
        self._export_button.setEnabled(enabled)

    def _update_export_button_state(self) -> None:
        """Enable the Export button only when export is possible."""

        can_export = (
            self._controller.is_available
            and self._controller.output_path is not None
            and self._controller.export_frame_count > 0
        )
        self._export_button.setEnabled(can_export)
