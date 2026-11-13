"""Preprocessing section accordion of the right panel"""

from typing import TYPE_CHECKING

from apkit4d.gui.shared.components.v_separator import VSeparator
from apkit4d.gui.views.widgets.frame_slider import FrameSlider

if TYPE_CHECKING:
    from apkit4d.gui.views.panels.right_panel import RightPanel

from PySide6.QtCore import QSignalBlocker, Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.gui.models.pipeline_model import PipelineStep
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.preprocessing import BgMode, PreprocParams


def create_param_row(label_text: str, widget: QWidget, tooltip: str | None = None) -> QWidget:
    row = QWidget()
    if tooltip:
        row.setToolTip(tooltip)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(QLabel(label_text), stretch=1)
    layout.addWidget(widget, stretch=1)
    return row


class PreprocessingSection(AccordionSection):
    """The preprocessing accordion"""

    def __init__(self, right_panel: RightPanel):
        super().__init__(texts.STAGE_TITLE_PREPROCESSING)

        self.right_panel = right_panel
        self.step = PipelineStep.PREPROCESSING
        play_btn = self.enable_play_button(
            callback=lambda s=self.step: self.right_panel._on_play_clicked(s),
            tooltip=texts.TOOLTIP_PLAY_STAGE,
        )

        # TODO: this doesn't do anything right now
        self.right_panel._play_buttons[PipelineStep.PREPROCESSING] = play_btn
        self.right_panel._plan_buttons[PipelineStep.PREPROCESSING] = play_btn

        # widgets
        self.denoise_xy_scale_um: QDoubleSpinBox
        self.denoise_z_scale_um: QDoubleSpinBox
        self.bg_mode: QComboBox
        self.bg_percentile: QDoubleSpinBox
        self.bg_sigma_xy_um: QDoubleSpinBox
        self.normalization_enabled: QCheckBox
        self.lowest_intensity: QDoubleSpinBox
        self.highest_intensity: QDoubleSpinBox
        self.logarithmic_compression_enabled: QCheckBox
        self.gamma_correction_to_apply: FrameSlider
        self.gamma_value_label: QLabel
        self.clahe_enabled: QCheckBox
        self.clahe_clip: QDoubleSpinBox
        self.clahe_kernel_xy_um: QDoubleSpinBox

        self._widgets()

    def get_preproc_params(self) -> PreprocParams:
        """Retrieve the preprocessing parameters."""

        try:
            bg_mode = BgMode(self.bg_mode.currentText())
        except ValueError:
            bg_mode = BgMode.NONE

        return PreprocParams(
            denoise_xy_scale_um=self.denoise_xy_box.value(),
            denoise_z_scale_um=self.denoise_z_box.value(),
            bg_mode=bg_mode,
            bg_percentile=self.bg_percentile.value(),
            bg_sigma_xy_um=self.bg_sigma_xy_um.value(),
            normalization_enabled=self.normalization_enabled.isChecked(),
            lowest_intensity=self.lowest_instensity.value(),
            highest_intensity=self.highest_intensity.value(),
            logarithmic_compression_enabled=self.logarithmic_compression_enabled.isChecked(),
            gamma_correction_to_apply=round(self.gamma_correction_to_apply.value() / 100.0, 2),
            clahe_enabled=self.clahe_enabled.isChecked(),
            clahe_clip=self.clahe_clip.value(),
            clahe_kernel_xy_um=self.clahe_kernel_xy_um.value(),
        )

    def set_preproc_params(self, params: PreprocParams) -> None:
        """Update preprocessing widget values from `params` without triggering change signals."""

        with QSignalBlocker(self.denoise_xy_box):
            self.denoise_xy_box.setValue(params.denoise_xy_scale_um)
        with QSignalBlocker(self.denoise_z_box):
            self.denoise_z_box.setValue(params.denoise_z_scale_um)
        with QSignalBlocker(self.bg_mode):
            self.bg_mode.setCurrentText(
                params.bg_mode.value if isinstance(params.bg_mode, BgMode) else str(params.bg_mode)
            )
        with QSignalBlocker(self.bg_percentile):
            self.bg_percentile.setValue(params.bg_percentile)
        with QSignalBlocker(self.bg_sigma_xy_um):
            self.bg_sigma_xy_um.setValue(params.bg_sigma_xy_um)
        with QSignalBlocker(self.normalization_enabled):
            self.normalization_enabled.setChecked(params.normalization_enabled)
        with QSignalBlocker(self.lowest_instensity):
            self.lowest_instensity.setValue(params.lowest_intensity)
        with QSignalBlocker(self.highest_intensity):
            self.highest_intensity.setValue(params.highest_intensity)
        with QSignalBlocker(self.logarithmic_compression_enabled):
            self.logarithmic_compression_enabled.setChecked(params.logarithmic_compression_enabled)
        with QSignalBlocker(self.gamma_correction_to_apply):
            self.gamma_correction_to_apply.setValue(int(round(params.gamma_correction_to_apply * 100.0)))
            self.gamma_value_label.setText(f"{params.gamma_correction_to_apply:.2f}")
        with QSignalBlocker(self.clahe_enabled):
            self.clahe_enabled.setChecked(params.clahe_enabled)
        with QSignalBlocker(self.clahe_clip):
            self.clahe_clip.setValue(params.clahe_clip)
        with QSignalBlocker(self.clahe_kernel_xy_um):
            self.clahe_kernel_xy_um.setValue(params.clahe_kernel_xy_um)

        self._update_preproc_enabled_states()

    def _update_preproc_enabled_states(self) -> None:
        """Update enabled states of dependent preprocessing controls."""

        bg_mode = self.bg_mode.currentText()
        self.bg_percentile.setEnabled(bg_mode == BgMode.PERCENTILE_PER_SLICE.value)
        self.bg_sigma_xy_um.setEnabled(bg_mode == BgMode.WIDE_GAUSSIAN.value)

        normalization_on = self.normalization_enabled.isChecked()
        self.lowest_instensity.setEnabled(normalization_on)
        self.highest_intensity.setEnabled(normalization_on)
        self.clahe_enabled.setEnabled(normalization_on)  # normalization is required for CLAHE

        clahe_on = self.clahe_enabled.isChecked() and normalization_on
        self.clahe_clip.setEnabled(clahe_on)
        self.clahe_kernel_xy_um.setEnabled(clahe_on)

    def _on_bg_mode_changed(self, mode_str: str) -> None:
        self._update_preproc_enabled_states()
        try:
            mode = BgMode(mode_str)
        except ValueError:
            mode = BgMode.NONE
        self.right_panel.step_param_changed.emit(PipelineStep.PREPROCESSING.value, "bg_mode", mode)

    def _on_clahe_toggled(self, checked: bool) -> None:
        self._update_preproc_enabled_states()
        self.right_panel.step_param_changed.emit(PipelineStep.PREPROCESSING.value, "clahe_enabled", checked)

    def _on_normalization_toggled(self, checked: bool) -> None:
        self._update_preproc_enabled_states()
        self.right_panel.step_param_changed.emit(
            PipelineStep.PREPROCESSING.value, "normalization_enabled", checked
        )

    def _on_gamma_slider_changed(self, int_val: int) -> None:
        gamma_val = round(int_val / 100.0, 2)
        self.gamma_value_label.setText(f"{gamma_val:.2f}")
        self.right_panel.step_param_changed.emit(self.step.value, "gamma_correction_to_apply", gamma_val)

    def _widgets(self):
        defaults = PreprocParams()

        # 1. Denoising
        self.denoise_xy_box = QDoubleSpinBox()
        self.denoise_xy_box.setObjectName(names.PREPROC_DENOISE_XY_FIELD)
        self.denoise_xy_box.setRange(0.0, 100.0)
        self.denoise_xy_box.setSingleStep(0.5)
        self.denoise_xy_box.setDecimals(2)
        self.denoise_xy_box.setValue(defaults.denoise_xy_scale_um)
        self.denoise_xy_box.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(
                s.value, "denoise_xy_scale_um", val
            )
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_DENOISE_XY, self.denoise_xy_box, texts.PREPROC_DENOISE_XY_TOOLTIP
            )
        )

        self.denoise_z_box = QDoubleSpinBox()
        self.denoise_z_box.setObjectName(names.PREPROC_DENOISE_Z_FIELD)
        self.denoise_z_box.setRange(0.0, 200.0)
        self.denoise_z_box.setSingleStep(0.5)
        self.denoise_z_box.setDecimals(2)
        self.denoise_z_box.setValue(defaults.denoise_z_scale_um)
        self.denoise_z_box.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(
                s.value, "denoise_z_scale_um", val
            )
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_DENOISE_Z, self.denoise_z_box, texts.PREPROC_DENOISE_Z_TOOLTIP
            )
        )

        self.add_widget(VSeparator())

        # 2. Background Removal
        self.bg_mode = QComboBox()
        self.bg_mode.setObjectName(names.PREPROC_BG_MODE_COMBO)
        for mode in BgMode:
            self.bg_mode.addItem(mode.value)
        self.bg_mode.setCurrentText(defaults.bg_mode.value)
        self.bg_mode.currentTextChanged.connect(self._on_bg_mode_changed)
        self.add_widget(
            create_param_row(texts.LABEL_PREPROC_BG_MODE, self.bg_mode, texts.PREPROC_DENOISE_BG_MODE_TOOLTIP)
        )

        self.bg_percentile = QDoubleSpinBox()
        self.bg_percentile.setObjectName(names.PREPROC_BG_PERCENTILE_FIELD)
        self.bg_percentile.setRange(0.0, 100.0)
        self.bg_percentile.setSingleStep(1.0)
        self.bg_percentile.setDecimals(1)
        self.bg_percentile.setValue(defaults.bg_percentile)
        self.bg_percentile.setEnabled(defaults.bg_mode == BgMode.PERCENTILE_PER_SLICE)
        self.bg_percentile.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(s.value, "bg_percentile", val)
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_BG_PERCENTILE,
                self.bg_percentile,
                texts.PREPROC_BG_PERCENTILE_TOOLTIP,
            )
        )

        self.bg_sigma_xy_um = QDoubleSpinBox()
        self.bg_sigma_xy_um.setObjectName(names.PREPROC_BG_SIGMA_XY_FIELD)
        self.bg_sigma_xy_um.setRange(1.0, 1000.0)
        self.bg_sigma_xy_um.setSingleStep(5.0)
        self.bg_sigma_xy_um.setDecimals(1)
        self.bg_sigma_xy_um.setValue(defaults.bg_sigma_xy_um)
        self.bg_sigma_xy_um.setEnabled(defaults.bg_mode == BgMode.WIDE_GAUSSIAN)
        self.bg_sigma_xy_um.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(s.value, "bg_sigma_xy_um", val)
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_BG_SIGMA_XY,
                self.bg_sigma_xy_um,
                texts.PREPROC_BG_WIDE_GAUSSIAN_TOOLTIP,
            )
        )

        self.add_widget(VSeparator())

        self.normalization_enabled = QCheckBox(texts.LABEL_PREPROC_NORMALIZATION_ENABLED)
        self.normalization_enabled.setToolTip(texts.PREPROC_NORMALIZATION_TOGGLE_TOOLTIP)
        self.normalization_enabled.setChecked(defaults.normalization_enabled)
        self.normalization_enabled.setObjectName(names.PREPROC_NORMALIZATION_ENABLED_FIELD)
        self.normalization_enabled.toggled.connect(self._on_normalization_toggled)
        self.add_widget(self.normalization_enabled)

        # 3. Intensity Windowing
        self.lowest_instensity = QDoubleSpinBox()
        self.lowest_instensity.setEnabled(defaults.normalization_enabled)
        self.lowest_instensity.setObjectName(names.PREPROC_LOWEST_INTENSITY_FIELD)
        self.lowest_instensity.setRange(0.0, 100000.0)
        self.lowest_instensity.setSingleStep(10.0)
        self.lowest_instensity.setDecimals(1)
        self.lowest_instensity.setValue(defaults.lowest_intensity)
        self.lowest_instensity.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(
                s.value, "lowest_intensity", val
            )
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_LOWEST_INTENSITY,
                self.lowest_instensity,
                texts.PREPROC_NORMALIZATION_TOGGLE_TOOLTIP,
            )
        )

        self.highest_intensity = QDoubleSpinBox()
        self.highest_intensity.setObjectName(names.PREPROC_HIGHEST_INTENSITY_FIELD)
        self.highest_intensity.setEnabled(defaults.normalization_enabled)
        self.highest_intensity.setRange(0.0, 100000.0)
        self.highest_intensity.setSingleStep(10.0)
        self.highest_intensity.setDecimals(1)
        self.highest_intensity.setValue(defaults.highest_intensity)
        self.highest_intensity.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(
                s.value, "highest_intensity", val
            )
        )
        self.add_widget(create_param_row(texts.LABEL_PREPROC_HIGHEST_INTENSITY, self.highest_intensity))

        # TODO: suggest window
        window = QPushButton("Suggest window")
        window.setObjectName("suggest_window")
        window.setToolTip("Press this button")
        self.add_widget(window)

        self.add_widget(VSeparator())

        # 4. Logarithmic compression
        self.logarithmic_compression_enabled = QCheckBox(texts.LABEL_PREPROC_LOG_COMPRESSION)
        self.logarithmic_compression_enabled.setObjectName(names.PREPROC_LOG_COMPRESSION_CHECKBOX)
        self.logarithmic_compression_enabled.setToolTip(texts.PREPROC_LOGARITHMIC_COMPRESSION_TOOLTIP)
        self.logarithmic_compression_enabled.setChecked(defaults.logarithmic_compression_enabled)
        self.logarithmic_compression_enabled.toggled.connect(
            lambda checked, s=self.step: self.right_panel.step_param_changed.emit(
                s.value, "logarithmic_compression_enabled", checked
            )
        )
        self.add_widget(self.logarithmic_compression_enabled)

        self.add_widget(VSeparator())

        # 5. Gamma
        gamma_container = QWidget()
        gamma_layout = QHBoxLayout(gamma_container)
        gamma_layout.setContentsMargins(0, 0, 0, 0)
        gamma_layout.setSpacing(8)

        self.gamma_correction_to_apply = FrameSlider(self)
        self.gamma_correction_to_apply.setObjectName(names.PREPROC_GAMMA_FIELD)
        self.gamma_correction_to_apply.setRange(10, 500)
        self.gamma_correction_to_apply.setSingleStep(5)
        self.gamma_correction_to_apply.setValue(int(round(defaults.gamma_correction_to_apply * 100.0)))
        self.gamma_correction_to_apply.valueChanged.connect(self._on_gamma_slider_changed)

        self.gamma_value_label = QLabel(f"{defaults.gamma_correction_to_apply:.2f}")
        self.gamma_value_label.setFixedWidth(36)
        self.gamma_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignBottom)
        self.gamma_value_label.setContentsMargins(0, 0, 0, 4)

        gamma_layout.addWidget(self.gamma_correction_to_apply, stretch=1)
        gamma_layout.addWidget(self.gamma_value_label)

        self.add_widget(
            create_param_row(texts.LABEL_PREPROC_GAMMA, gamma_container, texts.PREPROC_GAMMA_TOOLTIP)
        )

        self.add_widget(VSeparator())

        # 6. CLAHE
        self.clahe_enabled = QCheckBox(texts.LABEL_PREPROC_CLAHE)
        self.clahe_enabled.setObjectName(names.PREPROC_CLAHE_CHECKBOX)
        self.clahe_enabled.setToolTip(texts.PREPROC_CLAHE_TOOLTIP)
        self.clahe_enabled.setChecked(defaults.clahe_enabled)
        self.clahe_enabled.toggled.connect(self._on_clahe_toggled)
        self.clahe_enabled.setEnabled(defaults.normalization_enabled)
        self.add_widget(self.clahe_enabled)

        self.clahe_clip = QDoubleSpinBox()
        self.clahe_clip.setObjectName(names.PREPROC_CLAHE_CLIP_FIELD)
        self.clahe_clip.setRange(0.001, 1.0)
        self.clahe_clip.setSingleStep(0.005)
        self.clahe_clip.setDecimals(3)
        self.clahe_clip.setValue(defaults.clahe_clip)
        self.clahe_clip.setEnabled(defaults.clahe_enabled)
        self.clahe_clip.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(s.value, "clahe_clip", val)
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_CLAHE_CLIP, self.clahe_clip, texts.PREPROC_CLAHE_CLIP_TOOLTIP
            )
        )

        self.clahe_kernel_xy_um = QDoubleSpinBox()
        self.clahe_kernel_xy_um.setObjectName(names.PREPROC_CLAHE_KERNEL_XY_FIELD)
        self.clahe_kernel_xy_um.setRange(10.0, 2000.0)
        self.clahe_kernel_xy_um.setSingleStep(10.0)
        self.clahe_kernel_xy_um.setDecimals(1)
        self.clahe_kernel_xy_um.setValue(defaults.clahe_kernel_xy_um)
        self.clahe_kernel_xy_um.setEnabled(defaults.clahe_enabled)
        self.clahe_kernel_xy_um.valueChanged.connect(
            lambda val, s=self.step: self.right_panel.step_param_changed.emit(
                s.value, "clahe_kernel_xy_um", val
            )
        )
        self.add_widget(
            create_param_row(
                texts.LABEL_PREPROC_CLAHE_KERNEL_XY,
                self.clahe_kernel_xy_um,
                texts.PREPROC_CLAHE_KERNEL_TOOLTIP,
            )
        )

        self.add_widget(VSeparator())

        reset_btn = QPushButton(texts.PREPROC_RESET)
        reset_btn.setObjectName(names.PREPROC_RESET)
        reset_btn.clicked.connect(lambda: self._on_reset(defaults))
        self.add_widget(reset_btn)

        # TODO: complete button doesn't do anything right now
        complete_btn = QPushButton(texts.BUTTON_COMPLETE_STAGE)
        complete_btn.setObjectName(names.COMPLETE_STAGE_BUTTON)
        complete_btn.setToolTip(texts.TOOLTIP_COMPLETE_STAGE)
        complete_btn.clicked.connect(lambda _, s=self.step: self.right_panel.complete_stage_requested.emit(s))
        self.add_widget(complete_btn)
        self.right_panel._complete_buttons[self.step] = complete_btn

    def _on_reset(self, defaults: PreprocParams):
        self.set_preproc_params(defaults)
        self.right_panel.step_params_reset.emit(self.step.value)
