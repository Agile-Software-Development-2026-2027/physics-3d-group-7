"""Dialog for configuring frame loading strategies."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.gui.models.frame_loading_config import (
    FrameLoadingConfig,
    FrameLoadingMode,
)
from apkit4d.gui.views.widgets.wheel_guard import install_wheel_guard


class PerformanceSettingsDialog(QDialog):
    """Dialog for configuring frame loading and memory usage."""

    def __init__(
        self,
        config: FrameLoadingConfig,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.setObjectName(names.PERFORMANCE_DIALOG)
        self.setWindowTitle(texts.PERFORMANCE_DIALOG_TITLE)
        self.setMinimumWidth(400)

        layout = QVBoxLayout(self)
        self._form = QFormLayout()
        layout.addLayout(self._form)

        self._mode_combo = QComboBox()
        self._mode_combo.setObjectName(names.PERFORMANCE_MODE)
        self._mode_combo.addItem(
            texts.PERFORMANCE_MODE_LAZY,
            FrameLoadingMode.LAZY.value,
        )
        self._mode_combo.addItem(
            texts.PERFORMANCE_MODE_AUTOMATIC,
            FrameLoadingMode.AUTOMATIC.value,
        )
        self._mode_combo.addItem(
            texts.PERFORMANCE_MODE_MANUAL,
            FrameLoadingMode.MANUAL.value,
        )
        self._mode_combo.addItem(
            texts.PERFORMANCE_MODE_FULL,
            FrameLoadingMode.FULL.value,
        )
        descriptions = {
            FrameLoadingMode.LAZY: texts.PERFORMANCE_DESCRIPTION_LAZY,
            FrameLoadingMode.AUTOMATIC: texts.PERFORMANCE_DESCRIPTION_AUTOMATIC,
            FrameLoadingMode.MANUAL: texts.PERFORMANCE_DESCRIPTION_MANUAL,
            FrameLoadingMode.FULL: texts.PERFORMANCE_DESCRIPTION_FULL,
        }

        for mode, description in descriptions.items():
            self._mode_combo.setItemData(
                self._mode_combo.findData(mode.value),
                description,
                Qt.ItemDataRole.ToolTipRole,
            )

        self._form.addRow(
            texts.PERFORMANCE_LOADING_MODE,
            self._mode_combo,
        )

        self._settings_separator = QFrame()
        self._settings_separator.setFrameShape(QFrame.Shape.HLine)
        self._settings_separator.setFrameShadow(QFrame.Shadow.Sunken)
        self._form.addRow(self._settings_separator)

        self._lookahead_spin = QDoubleSpinBox()
        self._lookahead_spin.setObjectName(names.PERFORMANCE_LOOKAHEAD)
        self._lookahead_spin = QDoubleSpinBox()
        self._lookahead_spin.setObjectName(names.PERFORMANCE_LOOKAHEAD)
        self._lookahead_spin.setToolTip(texts.PERFORMANCE_TOOLTIP_LOOKAHEAD)
        self._lookahead_spin.setRange(0.1, 60.0)
        self._lookahead_spin.setSingleStep(0.5)
        self._form.addRow(
            texts.PERFORMANCE_LOOKAHEAD,
            self._lookahead_spin,
        )

        self._cache_limit_spin = QDoubleSpinBox()
        self._cache_limit_spin.setObjectName(names.PERFORMANCE_CACHE_LIMIT)
        self._cache_limit_spin = QDoubleSpinBox()
        self._cache_limit_spin.setObjectName(names.PERFORMANCE_CACHE_LIMIT)
        self._cache_limit_spin.setToolTip(texts.PERFORMANCE_TOOLTIP_CACHE_LIMIT)
        self._cache_limit_spin.setRange(0.1, 16384.0)
        self._form.addRow(
            texts.PERFORMANCE_CACHE_LIMIT,
            self._cache_limit_spin,
        )

        self._memory_reserve_spin = QSpinBox()
        self._memory_reserve_spin.setObjectName(names.PERFORMANCE_MEMORY_RESERVE)
        self._memory_reserve_spin = QSpinBox()
        self._memory_reserve_spin.setObjectName(names.PERFORMANCE_MEMORY_RESERVE)
        self._memory_reserve_spin.setToolTip(texts.PERFORMANCE_TOOLTIP_MEMORY_RESERVE)
        self._memory_reserve_spin.setRange(1, 99)
        self._form.addRow(
            texts.PERFORMANCE_MEMORY_RESERVE,
            self._memory_reserve_spin,
        )

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.RestoreDefaults
        )
        buttons.setObjectName(names.PERFORMANCE_BUTTONS)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore_defaults
        )
        layout.addWidget(buttons)

        self._load_config(config)

        self._mode_combo.currentIndexChanged.connect(self._update_visible_fields)
        self._update_visible_fields()

        self._wheel_guard = install_wheel_guard(self)

    def _load_config(self, config: FrameLoadingConfig) -> None:
        """Load configuration values into the dialog."""
        self._mode_combo.setCurrentIndex(self._mode_combo.findData(config.mode.value))
        self._lookahead_spin.setValue(config.lookahead_seconds)
        self._cache_limit_spin.setValue(config.cache_limit_gb)
        self._memory_reserve_spin.setValue(config.memory_reserve_percent)

    def _restore_defaults(self) -> None:
        """Restore the default frame loading configuration."""
        self._load_config(FrameLoadingConfig())

    def _update_visible_fields(self) -> None:
        """Show only settings relevant to the selected loading mode."""
        mode = FrameLoadingMode(self._mode_combo.currentData())

        description = self._mode_combo.currentData(Qt.ItemDataRole.ToolTipRole)
        self._mode_combo.setToolTip(description)

        self._form.setRowVisible(
            self._settings_separator,
            mode != FrameLoadingMode.LAZY,
        )

        self._form.setRowVisible(
            self._lookahead_spin,
            mode in (FrameLoadingMode.AUTOMATIC, FrameLoadingMode.MANUAL),
        )
        self._form.setRowVisible(
            self._cache_limit_spin,
            mode == FrameLoadingMode.MANUAL,
        )
        self._form.setRowVisible(
            self._memory_reserve_spin,
            mode
            in (
                FrameLoadingMode.AUTOMATIC,
                FrameLoadingMode.MANUAL,
                FrameLoadingMode.FULL,
            ),
        )

    def config(self) -> FrameLoadingConfig:
        """Return the configuration selected by the user."""
        return FrameLoadingConfig(
            mode=FrameLoadingMode(self._mode_combo.currentData()),
            lookahead_seconds=self._lookahead_spin.value(),
            cache_limit_gb=self._cache_limit_spin.value(),
            memory_reserve_percent=self._memory_reserve_spin.value(),
        )
