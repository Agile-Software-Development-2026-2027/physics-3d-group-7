"""Unit and integration tests for VisSubRoiController and MainController Sub-ROI wiring."""

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import pyvista as pv
from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QPushButton

from apkit4d.core.roi import Bounds6D, RegionOfInterest
from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.vis_sub_roi_controller import (
    VisSubRoiController,
    VisSubRoiView,
)
from apkit4d.gui.models.pipeline_model import PIPELINE_STEP_ORDER, PipelineModel, PipelineStep, StepStatus
from apkit4d.gui.views.display.vis_sub_roi_section import VisSubRoiSection
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.visualization.viewport import RoiMode, Viewport, VisSubRoiMode
from apkit4d.visualization.vis_sub_roi import (
    DEFAULT_OUTSIDE_OPACITY,
    VisSubRoiState,
    clamp_outside_opacity,
)


class _FakeFileController(QObject):
    loaded = Signal(object, object)
    closed = Signal()


class _FakeVisSubRoiView(QObject):
    """Deterministic VisSubRoiView double for unit-testing VisSubRoiController."""

    displayed_volume_bounds_updated = Signal(object)
    vis_sub_roi_selection_started = Signal()
    vis_sub_roi_bounds_changed = Signal(object)
    vis_sub_roi_interaction_ended = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._state = VisSubRoiState(
            enabled=False,
            bounds=None,
            outside_opacity=DEFAULT_OUTSIDE_OPACITY,
        )
        self.displayed_bounds: Bounds6D | None = None
        self.box_visible: bool = False
        self.box_bounds: Bounds6D | None = None
        self.selection_starts: int = 0
        self.stop_calls: int = 0
        self.clear_calls: int = 0
        self.reset_calls: int = 0
        self.events: list[str] = []

    @property
    def vis_sub_roi_state(self) -> VisSubRoiState:
        return self._state

    def set_vis_sub_roi_state(self, state: VisSubRoiState) -> None:
        clamped = (
            state.with_clamped_bounds(self.displayed_bounds) if self.displayed_bounds is not None else state
        )
        self._state = clamped

    def set_vis_sub_roi_enabled(self, enabled: bool) -> None:
        self.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=bool(enabled),
                bounds=self._state.bounds,
                outside_opacity=self._state.outside_opacity,
            )
        )

    def set_vis_sub_roi_bounds(self, bounds: Bounds6D | None) -> None:
        self.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=self._state.enabled,
                bounds=bounds,
                outside_opacity=self._state.outside_opacity,
            )
        )

    def set_vis_sub_roi_outside_opacity(self, outside_opacity: float) -> None:
        self.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=self._state.enabled,
                bounds=self._state.bounds,
                outside_opacity=clamp_outside_opacity(outside_opacity),
            )
        )

    def clear_vis_sub_roi(self) -> None:
        self.clear_calls += 1
        self.stop_vis_sub_roi_interaction()
        self.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=False,
                bounds=None,
                outside_opacity=self._state.outside_opacity,
            )
        )

    def reset_vis_sub_roi_state(self) -> None:
        self.reset_calls += 1
        self.stop_vis_sub_roi_interaction()
        self.set_vis_sub_roi_state(
            VisSubRoiState(
                enabled=False,
                bounds=None,
                outside_opacity=DEFAULT_OUTSIDE_OPACITY,
            )
        )

    def start_vis_sub_roi_selection(self) -> None:
        self.selection_starts += 1
        self.events.append("start_selection")
        self.vis_sub_roi_selection_started.emit()

    def stop_vis_sub_roi_interaction(self) -> None:
        self.stop_calls += 1
        was_visible = self.box_visible
        self.box_visible = False
        if was_visible:
            self.vis_sub_roi_interaction_ended.emit()

    def show_vis_sub_roi_box(self, bounds: Bounds6D | None = None) -> None:
        target = bounds if bounds is not None else self._state.bounds
        if target is None:
            return
        self.box_visible = True
        self.box_bounds = target

    def set_vis_sub_roi_box_visible(self, visible: bool, bounds: Bounds6D | None = None) -> None:
        if visible:
            self.show_vis_sub_roi_box(bounds)
        else:
            self.stop_vis_sub_roi_interaction()

    def emit_displayed_bounds(self, bounds: Bounds6D) -> None:
        self.displayed_bounds = bounds
        self.displayed_volume_bounds_updated.emit(bounds)


def _complete_all_steps(model: PipelineModel) -> None:
    for step in PIPELINE_STEP_ORDER:
        model.set_step_status(step, StepStatus.COMPLETED)


def _make_harness(qtbot, *, with_view: bool = True):
    section = VisSubRoiSection()
    qtbot.addWidget(section)
    model = PipelineModel()
    file_ctrl = _FakeFileController()
    view = _FakeVisSubRoiView() if with_view else None
    if view is not None:
        assert isinstance(view, VisSubRoiView)

    controller = VisSubRoiController(
        section=section,
        pipeline_model=model,
        file_controller=file_ctrl,  # type: ignore[arg-type]
        view=view,
    )
    return SimpleNamespace(
        controller=controller,
        section=section,
        model=model,
        file_ctrl=file_ctrl,
        view=view,
    )


# sub-roi readiness requires both displayed bounds and completed detection step
def test_readiness_requires_clean_detection_and_displayed_bounds(qtbot) -> None:
    h = _make_harness(qtbot)
    assert h.controller.is_available is False
    assert h.section.is_available is False

    # Displayed bounds alone are not enough
    h.view.emit_displayed_bounds((0.0, 50.0, 0.0, 40.0, 0.0, 20.0))
    assert h.controller.is_available is False
    assert h.section.is_available is False

    # Completing ROI and PREPROCESSING without DETECTION is still not enough
    h.model.set_step_status(PipelineStep.ROI, StepStatus.COMPLETED)
    h.model.set_step_status(PipelineStep.PREPROCESSING, StepStatus.COMPLETED)
    assert h.controller.is_available is False
    assert h.section.is_available is False

    # Completing DETECTION unlocks the section even before TRACKING and BATCH run
    h.model.set_step_status(PipelineStep.DETECTION, StepStatus.COMPLETED)
    assert h.controller.is_available is True
    assert h.section.is_available is True


# editing a parameter in a completed pipeline makes the step dirty,
# which locks the controller and disables the effect while preserving bounds and opacity
def test_dirty_step_locks_and_disables_effect_while_preserving_bounds_and_opacity(qtbot) -> None:
    h = _make_harness(qtbot)
    h.view.emit_displayed_bounds((0.0, 50.0, 0.0, 40.0, 0.0, 20.0))
    _complete_all_steps(h.model)

    # Configure active Sub-ROI state
    h.section.findChild(FrameSlider, names.VIS_SUB_ROI_OPACITY_SLIDER).setValue(20)
    h.section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN).setValue(10.0)
    assert h.view.vis_sub_roi_state.enabled is True
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((10.0, 50.0, 0.0, 40.0, 0.0, 20.0))
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.20)
    assert h.view.box_visible is True

    # Editing a parameter makes PREPROCESSING dirty even though PipelineModel.is_complete stays True
    original_gamma = h.model.get_preproc_params().gamma_correction_to_apply
    h.model.update_step_params(PipelineStep.PREPROCESSING, gamma_correction_to_apply=original_gamma + 0.5)
    assert h.model.is_complete is True
    assert h.model.is_step_dirty(PipelineStep.PREPROCESSING) is True

    assert h.controller.is_available is False
    assert h.section.is_available is False
    assert h.view.box_visible is False
    assert h.view.vis_sub_roi_state.enabled is False
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((10.0, 50.0, 0.0, 40.0, 0.0, 20.0))
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.20)

    # Reverting parameter clears dirty flag ->
    # unlocks again with bounds/opacity preserved and enabled=False
    h.model.update_step_params(PipelineStep.PREPROCESSING, gamma_correction_to_apply=original_gamma)
    assert h.controller.is_available is True
    assert h.section.is_available is True
    assert h.view.vis_sub_roi_state.enabled is False
    assert h.section.is_sub_roi_enabled is False
    assert h.section.bounds == pytest.approx((10.0, 50.0, 0.0, 40.0, 0.0, 20.0))
    assert h.section.outside_opacity == pytest.approx(0.20)


# enabling the effect without prior bounds initializes bounds to displayed volume bounds,
# and editing a spinbox immediately re-enables the effect with updated bounds
def test_enable_without_prior_bounds_and_spinbox_edits_apply_live_without_touching_pipeline(qtbot) -> None:
    h = _make_harness(qtbot)
    h.view.emit_displayed_bounds((5.0, 45.0, 2.0, 32.0, 1.0, 11.0))
    _complete_all_steps(h.model)

    # Change outside opacity first
    slider = h.section.findChild(FrameSlider, names.VIS_SUB_ROI_OPACITY_SLIDER)
    assert slider is not None
    slider.setValue(15)
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.15)
    assert h.view.vis_sub_roi_state.bounds is None

    # Enabling directly with bounds=None initializes bounds to displayed volume bounds & shows box
    checkbox = h.section.findChild(QCheckBox, names.VIS_SUB_ROI_ENABLED_CHECKBOX)
    assert checkbox is not None
    checkbox.setChecked(True)

    assert h.view.vis_sub_roi_state.enabled is True
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((5.0, 45.0, 2.0, 32.0, 1.0, 11.0))
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.15)
    assert h.view.box_visible is True

    # Disabling hides box while preserving bounds & opacity
    checkbox.setChecked(False)
    assert h.view.vis_sub_roi_state.enabled is False
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((5.0, 45.0, 2.0, 32.0, 1.0, 11.0))
    assert h.view.box_visible is False

    # Editing a spinbox immediately re-enables effect, updates bounds, shows box, keeps opacity
    x_min = h.section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN)
    assert x_min is not None
    x_min.setValue(12.0)

    assert h.view.vis_sub_roi_state.enabled is True
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((12.0, 45.0, 2.0, 32.0, 1.0, 11.0))
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.15)
    assert h.section.is_sub_roi_enabled is True
    assert h.view.box_visible is True
    assert h.model.is_complete is True


# Test that the 3 different ways to reset the sub-ROI have distinct semantics:
# click reset button, pipeline reset, and session close / new file
def test_distinct_reset_semantics_vis_reset_pipeline_reset_and_session_reset(qtbot) -> None:
    h = _make_harness(qtbot)
    bounds = (0.0, 40.0, 0.0, 40.0, 0.0, 20.0)
    h.view.emit_displayed_bounds(bounds)
    _complete_all_steps(h.model)

    h.section.findChild(FrameSlider, names.VIS_SUB_ROI_OPACITY_SLIDER).setValue(30)
    h.section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN).setValue(8.0)

    # 1. VIS_SUB_ROI Reset button: clears bounds, disables effect, preserves outside_opacity,
    # leaves pipeline complete
    reset_btn = h.section.findChild(QPushButton, names.VIS_SUB_ROI_RESET_BUTTON)
    assert reset_btn is not None
    reset_btn.click()

    assert h.view.clear_calls == 1
    assert h.view.vis_sub_roi_state == VisSubRoiState(enabled=False, bounds=None, outside_opacity=0.30)
    assert h.section.is_available is True
    assert h.section.is_sub_roi_enabled is False
    assert h.section.outside_opacity == pytest.approx(0.30)
    assert h.section.bounds == pytest.approx(bounds)
    assert h.model.is_complete is True

    # 2. Pipeline reset: locks UI, disables effect, preserves bounds & outside_opacity
    # (does NOT call clear_vis_sub_roi)
    h.section.findChild(QDoubleSpinBox, names.VIS_SUB_ROI_X_MIN).setValue(12.0)
    clear_calls_before = h.view.clear_calls
    h.model.reset_all()

    assert h.view.clear_calls == clear_calls_before
    assert h.controller.is_available is False
    assert h.section.is_available is False
    assert h.view.box_visible is False
    assert h.view.vis_sub_roi_state.enabled is False
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((12.0, 40.0, 0.0, 40.0, 0.0, 20.0))
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.30)

    # 3. Session close / new file: full default reset including outside_opacity=0.01 and displayed_bounds=None
    h.file_ctrl.closed.emit()
    assert h.view.reset_calls == 1
    assert h.controller.displayed_volume_bounds is None
    assert h.view.vis_sub_roi_state == VisSubRoiState(
        enabled=False,
        bounds=None,
        outside_opacity=DEFAULT_OUTSIDE_OPACITY,
    )
    assert h.section.outside_opacity == pytest.approx(DEFAULT_OUTSIDE_OPACITY)
    assert h.section.is_available is False


# Test that repeated identical displayed bounds during playback are deduplicated,
# and that closing and loading a new file with identical geometry unlocks the controller
def test_identical_bounds_after_new_file_unlock_controller_and_deduplicate_frame_updates(
    qtbot, monkeypatch
) -> None:
    h = _make_harness(qtbot)
    same_bounds = (0.0, 30.0, 0.0, 30.0, 0.0, 10.0)

    set_vol_calls: list[Bounds6D] = []
    orig_set_vol = h.section.set_volume_bounds

    def _spy_set_volume_bounds(b: Bounds6D) -> None:
        set_vol_calls.append(b)
        orig_set_vol(b)

    monkeypatch.setattr(h.section, "set_volume_bounds", _spy_set_volume_bounds)

    h.view.emit_displayed_bounds(same_bounds)
    calls_after_first = len(set_vol_calls)
    # Repeated identical bounds during playback are deduplicated
    h.view.emit_displayed_bounds(same_bounds)
    assert len(set_vol_calls) == calls_after_first

    # Close and load a new recording with identical geometry
    h.file_ctrl.closed.emit()
    h.file_ctrl.loaded.emit(Path("next.czi"), SimpleNamespace())
    assert h.controller.displayed_volume_bounds is None

    h.view.emit_displayed_bounds(same_bounds)
    assert h.controller.displayed_volume_bounds == same_bounds

    _complete_all_steps(h.model)
    assert h.controller.is_available is True
    assert h.section.is_available is True

    # DATA_ROI cropping changes displayed bounds -> updates spinbox ranges
    cropped_bounds = (5.0, 20.0, 4.0, 18.0, 2.0, 8.0)
    h.view.emit_displayed_bounds(cropped_bounds)
    assert h.controller.displayed_volume_bounds == cropped_bounds
    assert h.section.bounds == pytest.approx(cropped_bounds)


# tests the exact sequence of events when the user clicks the Select button
def test_select_emits_interaction_starting_before_viewport_and_syncs_viewport_updates(qtbot) -> None:
    h = _make_harness(qtbot)
    h.view.emit_displayed_bounds((0.0, 50.0, 0.0, 50.0, 0.0, 20.0))
    _complete_all_steps(h.model)

    h.controller.interaction_starting.connect(lambda: h.view.events.append("interaction_starting"))

    select_btn = h.section.findChild(QPushButton, names.VIS_SUB_ROI_SELECT_BUTTON)
    assert select_btn is not None
    select_btn.click()

    assert h.view.events == ["interaction_starting", "start_selection"]
    assert h.view.selection_starts == 1

    # Viewport updates must sync UI spinboxes without emitting bounds_edited back
    with qtbot.assertNotEmitted(h.section.bounds_edited):
        h.view.vis_sub_roi_bounds_changed.emit((5.0, 25.0, 4.0, 20.0, 2.0, 10.0))
    assert h.section.bounds == pytest.approx((5.0, 25.0, 4.0, 20.0, 2.0, 10.0))
    assert h.section.is_sub_roi_enabled is True

    # stop_interaction exits viewport box without altering VisSubRoiState
    h.view.set_vis_sub_roi_state(
        VisSubRoiState(enabled=True, bounds=(5.0, 25.0, 4.0, 20.0, 2.0, 10.0), outside_opacity=0.05)
    )
    h.view.show_vis_sub_roi_box()
    h.controller.stop_interaction()
    assert h.view.box_visible is False
    assert h.view.vis_sub_roi_state.bounds == pytest.approx((5.0, 25.0, 4.0, 20.0, 2.0, 10.0))
    assert h.view.vis_sub_roi_state.outside_opacity == pytest.approx(0.05)
    assert (
        h.section.findChild(type(h.section._status_label), names.VIS_SUB_ROI_STATUS_LABEL).text()
        == texts.STATUS_VIS_SUB_ROI_INACTIVE
    )


# Test that the controller and section gracefully handle the case where the viewport is missing
def test_controller_handles_missing_viewport_gracefully(qtbot) -> None:
    h = _make_harness(qtbot, with_view=False)
    _complete_all_steps(h.model)
    assert h.controller.is_available is False
    assert h.section.is_available is False
    h.controller.stop_interaction()
    h.file_ctrl.closed.emit()


# Test that the MainController wires the VisSubRoiController and enforces
# mutual exclusion with DataROI
def test_main_controller_wires_vis_sub_roi_and_mutual_exclusion_with_data_roi(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    vp = Viewport()
    qtbot.addWidget(vp)
    window.set_view(vp)

    try:
        mc = MainController(window, qapp, window, view=vp)
        section = window.left_panel.vis_sub_roi_section
        assert mc.vis_sub_roi_controller.is_available is False
        assert section.is_available is False

        # Display a volume and complete all pipeline stages
        grid = pv.ImageData(dimensions=(6, 6, 6))
        grid.point_data["values"] = np.ones(grid.n_points, dtype=np.float32)
        vp.show_volume(grid, reset_camera=False)
        _complete_all_steps(mc.pipeline_model)

        assert mc.vis_sub_roi_controller.is_available is True
        assert section.is_available is True

        # Enable VIS_SUB_ROI from LeftPanel -> shows box and enables effect without touching DATA_ROI
        checkbox = section.findChild(QCheckBox, names.VIS_SUB_ROI_ENABLED_CHECKBOX)
        assert checkbox is not None
        checkbox.setChecked(True)
        assert vp.vis_sub_roi_state.enabled is True
        assert vp.vis_sub_roi_box_visible is True
        assert mc.volume_controller is not None and mc.volume_controller.roi is None
        assert mc.pipeline_model.is_complete is True

        # DATA_ROI interaction starting stops VIS_SUB_ROI box interaction while preserving its state
        mc.roi_controller.roi_interaction_started.emit()
        assert vp.vis_sub_roi_box_visible is False
        assert vp.vis_sub_roi_mode == VisSubRoiMode.INACTIVE
        assert vp.vis_sub_roi_state.bounds is not None

        # Active DATA_ROI edit is cancelled through RoiStageController when starting VIS_SUB_ROI select
        vp.set_roi_preview(RegionOfInterest(0.5, 3.0, 0.5, 3.0, 0.5, 3.0))
        assert window.right_panel.roi_inspector is not None
        window.right_panel.roi_inspector.set_editing_mode(True)
        assert vp.roi_mode == RoiMode.EDITING

        select_btn = section.findChild(QPushButton, names.VIS_SUB_ROI_SELECT_BUTTON)
        assert select_btn is not None
        select_btn.click()

        assert vp.roi_mode == RoiMode.INACTIVE
        assert "roi_preview" not in vp.plotter.actors
        accept_btn = window.right_panel.roi_inspector.findChild(
            QPushButton, names.ROI_INSPECTOR_ACCEPT_BUTTON
        )
        assert accept_btn is not None and not accept_btn.isEnabled()
        assert vp.vis_sub_roi_mode == VisSubRoiMode.WAITING_FIRST_POINT
    finally:
        vp.plotter.close()


# Test that the MainController keeps the VisSubRoiController
# unavailable when the viewport is missing
def test_main_controller_without_viewport_keeps_vis_sub_roi_unavailable(qtbot, qapp) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    mc = MainController(window, qapp, window, view=None)

    _complete_all_steps(mc.pipeline_model)
    assert mc.vis_sub_roi_controller.is_available is False
    assert window.left_panel.vis_sub_roi_section.is_available is False
