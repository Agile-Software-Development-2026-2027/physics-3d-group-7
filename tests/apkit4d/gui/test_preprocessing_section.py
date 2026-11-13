import numpy as np
import pytest

from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.volume_controller import VolumeController
from apkit4d.gui.models.pipeline_model import PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.preprocessing import BgMode, PreprocParams


class SignalCatcher:
    def __init__(self, panel: RightPanel):
        self.signals = []
        panel.step_param_changed.connect(self._collect)

    def _collect(self, step_value: int, param_name: str, value):
        """Store emitted signal data for later inspection."""
        self.signals.append((step_value, param_name, value))

    def clear(self):
        self.signals.clear()

    def last(self):
        return self.signals[-1] if self.signals else None


@pytest.fixture
def right_panel(qtbot):
    rp = RightPanel()
    qtbot.addWidget(rp)
    rp.show()
    qtbot.wait(250)  # let initial DebouncedSlider(200) timer settle
    return rp


def test_preproc_defaults_match_preproc_params_dataclass_default(right_panel):
    section = right_panel.get_section(PipelineStep.PREPROCESSING)
    params = section.get_preproc_params()
    assert params == PreprocParams()


def test_widget_changes_emits_signal(right_panel: RightPanel, qtbot):
    section = right_panel.get_section(PipelineStep.PREPROCESSING)
    catcher = SignalCatcher(right_panel)

    section.denoise_xy_box.setValue(7.3)
    qtbot.waitUntil(lambda: catcher.last() is not None, timeout=2000)
    step, name, value = catcher.last()
    assert step == PipelineStep.PREPROCESSING.value
    assert name == "denoise_xy_scale_um"
    assert abs(value - 7.3) < 0.01
    catcher.clear()

    section.bg_mode.setCurrentText(BgMode.PERCENTILE_PER_SLICE.value)
    qtbot.waitUntil(lambda: catcher.last() is not None, timeout=2000)
    step, name, value = catcher.last()
    assert name == "bg_mode"
    assert isinstance(value, BgMode) and value == BgMode.PERCENTILE_PER_SLICE
    catcher.clear()

    section.clahe_enabled.setChecked(True)
    qtbot.wait(10)
    step, name, value = catcher.last()
    assert name == "clahe_enabled"
    assert value is True
    catcher.clear()

    section.gamma_correction_to_apply.setValue(185)
    assert catcher.last() is None

    qtbot.waitUntil(lambda: catcher.last() is not None, timeout=2000)
    step, name, value = catcher.last()
    assert name == "gamma_correction_to_apply"
    assert abs(value - 1.85) < 0.001
    assert section.gamma_value_label.text() == "1.85"


def test_set_params_without_emitting_signals(right_panel: RightPanel, qtbot):
    section = right_panel.get_section(PipelineStep.PREPROCESSING)
    catcher = SignalCatcher(right_panel)

    new_params = PreprocParams(
        denoise_xy_scale_um=1.1,
        denoise_z_scale_um=2.2,
        bg_mode=BgMode.WIDE_GAUSSIAN,
        bg_percentile=55.0,
        bg_sigma_xy_um=12.5,
        lowest_intensity=100.0,
        highest_intensity=9000.0,
        logarithmic_compression_enabled=True,
        gamma_correction_to_apply=1.7,
        clahe_enabled=True,
        clahe_clip=0.025,
        clahe_kernel_xy_um=25.0,
    )

    section.set_preproc_params(new_params)
    assert len(catcher.signals) == 0  # no signals emitted

    assert section.get_preproc_params() == new_params


def test_preproc_section_changes_are_propagated_through_the_main_controller(qtbot, qapp):
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window)

    section = window.right_panel.get_section(PipelineStep.PREPROCESSING)

    section.denoise_xy_box.setValue(4.5)
    qtbot.wait(10)

    model_params = controller.pipeline_model.get_preproc_params()
    assert abs(model_params.denoise_xy_scale_um - 4.5) < 0.01


def test_suggest_window_button_enabled_only_with_normalization(right_panel: RightPanel) -> None:
    section = right_panel.get_section(PipelineStep.PREPROCESSING)

    assert not section.normalization_enabled.isChecked()
    assert not section.suggest_window_btn.isEnabled()

    section.normalization_enabled.setChecked(True)
    assert section.suggest_window_btn.isEnabled()

    section.normalization_enabled.setChecked(False)
    assert not section.suggest_window_btn.isEnabled()


def test_set_intensity_window_updates_spinboxes_and_emits_params(right_panel: RightPanel) -> None:
    section = right_panel.get_section(PipelineStep.PREPROCESSING)
    catcher = SignalCatcher(right_panel)

    section.set_intensity_window(42.5, 875.0)

    assert section.lowest_instensity.value() == pytest.approx(42.5)
    assert section.highest_intensity.value() == pytest.approx(875.0)
    assert (PipelineStep.PREPROCESSING.value, "lowest_intensity", 42.5) in catcher.signals
    assert (PipelineStep.PREPROCESSING.value, "highest_intensity", 875.0) in catcher.signals


def test_clicking_suggest_window_populates_ui_and_updates_model(qtbot, qapp) -> None:
    class DummyVolumeView:
        def show_volume(self, grid, reset_camera: bool = True, force_update: bool = False) -> None:
            pass

    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window)

    vol_ctrl = VolumeController(window, DummyVolumeView(), controller)
    controller._volume_controller = vol_ctrl

    section = window.right_panel.get_section(PipelineStep.PREPROCESSING)
    section.suggest_window_clicked.connect(controller._on_suggest_window_clicked)
    vol_ctrl.window_suggested.connect(controller._on_window_suggested)

    vol = np.arange(1, 1001, dtype=np.uint16).reshape(10, 10, 10)
    vol_ctrl._usable = True
    vol_ctrl._current_roi_volume = vol

    section.normalization_enabled.setChecked(True)
    with qtbot.waitSignal(vol_ctrl.window_suggested, timeout=5000):
        section.suggest_window_btn.click()

    lo = section.lowest_instensity.value()
    hi = section.highest_intensity.value()
    assert lo == pytest.approx(10.99, rel=1e-2)
    assert hi == pytest.approx(999.001, rel=1e-2)

    params = controller.pipeline_model.get_preproc_params()
    assert params.lowest_intensity == pytest.approx(lo)
    assert params.highest_intensity == pytest.approx(hi)
