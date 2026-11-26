"""Tests for the performance settings dialog."""

import pytest
from PySide6.QtWidgets import QComboBox, QDialogButtonBox, QDoubleSpinBox, QSpinBox

from apkit4d.gui.constants import names
from apkit4d.gui.models.frame_loading_config import (
    FrameLoadingConfig,
    FrameLoadingMode,
)
from apkit4d.gui.views.widgets.dialogs.performance_settings_dialog import (
    PerformanceSettingsDialog,
)


@pytest.fixture
def dialog(qtbot):
    dialog = PerformanceSettingsDialog(FrameLoadingConfig())
    qtbot.addWidget(dialog)
    return dialog


def test_initial_config(qtbot) -> None:
    config = FrameLoadingConfig(
        mode=FrameLoadingMode.MANUAL,
        lookahead_seconds=5.0,
        cache_limit_gb=32.0,
        memory_reserve_percent=30,
    )

    dialog = PerformanceSettingsDialog(config)
    qtbot.addWidget(dialog)

    assert dialog.config() == config


@pytest.mark.parametrize(
    ("mode", "lookahead", "cache_limit", "memory_reserve"),
    [
        (FrameLoadingMode.LAZY, False, False, False),
        (FrameLoadingMode.AUTOMATIC, True, False, True),
        (FrameLoadingMode.MANUAL, True, True, True),
        (FrameLoadingMode.FULL, False, False, True),
    ],
)
def test_visible_fields(
    dialog,
    mode,
    lookahead,
    cache_limit,
    memory_reserve,
) -> None:
    mode_combo = dialog.findChild(QComboBox, names.PERFORMANCE_MODE)
    lookahead_spin = dialog.findChild(QDoubleSpinBox, names.PERFORMANCE_LOOKAHEAD)
    cache_limit_spin = dialog.findChild(QDoubleSpinBox, names.PERFORMANCE_CACHE_LIMIT)
    memory_reserve_spin = dialog.findChild(QSpinBox, names.PERFORMANCE_MEMORY_RESERVE)

    mode_combo.setCurrentIndex(mode_combo.findData(mode.value))

    assert lookahead_spin.isVisibleTo(dialog) == lookahead
    assert cache_limit_spin.isVisibleTo(dialog) == cache_limit
    assert memory_reserve_spin.isVisibleTo(dialog) == memory_reserve


def test_updated_config(dialog) -> None:
    mode_combo = dialog.findChild(QComboBox, names.PERFORMANCE_MODE)
    lookahead_spin = dialog.findChild(QDoubleSpinBox, names.PERFORMANCE_LOOKAHEAD)
    cache_limit_spin = dialog.findChild(QDoubleSpinBox, names.PERFORMANCE_CACHE_LIMIT)

    mode_combo.setCurrentIndex(mode_combo.findData(FrameLoadingMode.MANUAL.value))
    lookahead_spin.setValue(4.0)
    cache_limit_spin.setValue(64.0)

    assert dialog.config() == FrameLoadingConfig(
        mode=FrameLoadingMode.MANUAL,
        lookahead_seconds=4.0,
        cache_limit_gb=64.0,
    )


def test_values_preserved_when_switching_modes(dialog) -> None:
    mode_combo = dialog.findChild(QComboBox, names.PERFORMANCE_MODE)
    cache_limit_spin = dialog.findChild(QDoubleSpinBox, names.PERFORMANCE_CACHE_LIMIT)

    mode_combo.setCurrentIndex(mode_combo.findData(FrameLoadingMode.MANUAL.value))
    cache_limit_spin.setValue(32.0)

    mode_combo.setCurrentIndex(mode_combo.findData(FrameLoadingMode.LAZY.value))
    mode_combo.setCurrentIndex(mode_combo.findData(FrameLoadingMode.MANUAL.value))

    assert cache_limit_spin.value() == 32.0


def test_restore_defaults(qtbot) -> None:
    config = FrameLoadingConfig(
        mode=FrameLoadingMode.MANUAL,
        lookahead_seconds=5.0,
        cache_limit_gb=32.0,
        memory_reserve_percent=30,
    )

    dialog = PerformanceSettingsDialog(config)
    qtbot.addWidget(dialog)

    buttons = dialog.findChild(QDialogButtonBox, names.PERFORMANCE_BUTTONS)
    reset_button = buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults)

    reset_button.click()

    assert dialog.config() == FrameLoadingConfig()
