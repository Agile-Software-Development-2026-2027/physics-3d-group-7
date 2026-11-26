"""Unit tests for RoiStageController workflow, preview preservation, and model sync."""

from types import SimpleNamespace
from unittest.mock import MagicMock

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDoubleSpinBox, QLabel, QPushButton, QWidget

from apkit4d.core.frame_range import FrameRange
from apkit4d.core.models import RoiConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.roi_controller import RoiStageController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep, StepStatus
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.playback.playback_bar import PlaybackBar
from apkit4d.gui.views.stages.roi_inspector import RoiInspector


class FakeRoiView(QObject):
    """Minimal RoiSelectionView double for testing RoiStageController."""

    roi_updated = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.started = 0
        self.cancelled = 0
        self.previews: list[RegionOfInterest] = []
        self.pending_accept_roi: RegionOfInterest | None = None

    def start_roi_selection(self) -> None:
        self.started += 1

    def set_roi_preview(self, roi: RegionOfInterest) -> None:
        self.previews.append(roi)
        self.pending_accept_roi = roi

    def accept_roi_selection(self) -> RegionOfInterest | None:
        roi = self.pending_accept_roi
        self.pending_accept_roi = None
        return roi

    def cancel_roi_selection(self) -> None:
        self.cancelled += 1
        self.pending_accept_roi = None


def _make_harness(qtbot, *, with_source: bool = True):
    right_panel = RightPanel()
    qtbot.addWidget(right_panel)
    inspector = right_panel.roi_inspector
    assert isinstance(inspector, RoiInspector)

    playback_bar = PlaybackBar()
    qtbot.addWidget(playback_bar)

    pipeline_model = PipelineModel()
    pipeline_controller = PipelineController(pipeline_model, right_panel)
    playback_controller = PlaybackController(playback_bar)

    file_controller = MagicMock()
    file_controller.source = SimpleNamespace(info=SimpleNamespace(n_t=5)) if with_source else None

    volume_controller = MagicMock()
    volume_controller.roi = None
    volume_controller.volume_bounds_changed = FakeRoiView()  # replaced below with Signal host

    class _VolumeSignalHost(QObject):
        volume_bounds_changed = Signal(object)

        def __init__(self) -> None:
            super().__init__()
            self.roi: RegionOfInterest | None = None
            self.set_roi_calls: list[RegionOfInterest | None] = []

        def set_roi(self, roi: RegionOfInterest | None) -> None:
            self.roi = roi
            self.set_roi_calls.append(roi)

    vol_host = _VolumeSignalHost()
    roi_view = FakeRoiView()

    controller = RoiStageController(
        inspector=inspector,
        volume_controller=vol_host,  # type: ignore[arg-type]
        pipeline_model=pipeline_model,
        pipeline_controller=pipeline_controller,
        playback_controller=playback_controller,
        file_controller=file_controller,
        playback_bar=playback_bar,
        view=roi_view,
    )
    vol_host.volume_bounds_changed.emit((0.0, 100.0, 0.0, 80.0, 0.0, 40.0))

    return SimpleNamespace(
        controller=controller,
        inspector=inspector,
        vol=vol_host,
        roi_view=roi_view,
        model=pipeline_model,
        pipeline=pipeline_controller,
        playback_bar=playback_bar,
        playback=playback_controller,
        file_controller=file_controller,
    )


def _accept_bounds(h, roi: RegionOfInterest) -> None:
    h.inspector.set_roi_bounds(roi.bounds)
    h.roi_view.pending_accept_roi = None
    accept_btn = h.inspector.findChild(QPushButton, names.ROI_INSPECTOR_ACCEPT_BUTTON)
    assert accept_btn is not None
    h.inspector.set_editing_mode(True)
    accept_btn.click()


def test_cancel_after_spinbox_edit_preserves_previously_accepted_roi(qtbot) -> None:
    h = _make_harness(qtbot)
    accepted_roi = RegionOfInterest(x_min=10.0, x_max=50.0, y_min=10.0, y_max=40.0, z_min=5.0, z_max=25.0)
    _accept_bounds(h, accepted_roi)

    assert h.vol.roi == accepted_roi
    assert h.model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED

    # Edit spinbox manually to trigger preview without accepting
    x_min_spin = h.inspector.findChild(QDoubleSpinBox, names.ROI_INSPECTOR_X_MIN)
    assert x_min_spin is not None
    x_min_spin.setValue(20.0)

    assert len(h.roi_view.previews) == 1
    assert h.roi_view.previews[0].x_min == 20.0
    assert not h.playback_bar.isEnabled()
    # Critical: previewing must NOT wipe VolumeController.roi before Accept
    assert h.vol.roi == accepted_roi

    # Cancel must restore the previously accepted ROI in the inspector and keep VolumeController.roi
    cancel_btn = h.inspector.findChild(QPushButton, names.ROI_INSPECTOR_CANCEL_BUTTON)
    assert cancel_btn is not None
    cancel_btn.click()

    assert h.roi_view.cancelled == 1
    assert h.vol.roi == accepted_roi
    assert h.inspector.get_roi() == accepted_roi
    assert h.playback_bar.isEnabled()


def test_show_roi_crops_the_volume_and_fills_the_inspector_without_running_stage_1(qtbot) -> None:
    # the ROI of saved results: the stage status is restored by whoever opens them
    h = _make_harness(qtbot)
    _accept_bounds(h, RegionOfInterest(x_min=5.0, x_max=60.0, y_min=5.0, y_max=60.0, z_min=0.0, z_max=30.0))
    h.model.reset_all()
    saved = RegionOfInterest(x_min=10.0, x_max=50.0, y_min=10.0, y_max=40.0, z_min=5.0, z_max=25.0)

    h.controller.show_roi(saved)

    assert h.vol.roi == saved
    assert h.inspector.get_roi() == saved
    status = h.inspector.findChild(QLabel, names.ROI_INSPECTOR_STATUS_LABEL)
    assert status is not None and status.text() != texts.INSPECTOR_STATUS_ROI_FULL
    assert not h.controller.has_undo  # nothing to go back to: the ROI comes with the results
    assert h.model.get_status(PipelineStep.ROI) == StepStatus.IDLE


def test_reset_to_full_volume_syncs_pipeline_model(qtbot) -> None:
    h = _make_harness(qtbot)
    accepted_roi = RegionOfInterest(x_min=10.0, x_max=50.0, y_min=10.0, y_max=40.0, z_min=5.0, z_max=25.0)
    _accept_bounds(h, accepted_roi)
    h.pipeline.complete_stage(PipelineStep.PREPROCESSING)

    assert h.model.get_roi_params().region == accepted_roi
    assert h.model.get_status(PipelineStep.PREPROCESSING) == StepStatus.COMPLETED

    selected_range = FrameRange(1, 3)
    h.inspector.frames_selector.selected_frames_changed.emit(selected_range)

    assert h.model.get_roi_params().frame_range == selected_range

    reset_btn = h.inspector.findChild(QPushButton, names.ROI_INSPECTOR_RESET_BUTTON)
    assert reset_btn is not None
    reset_btn.click()

    assert h.vol.roi is None
    assert not h.controller.has_undo
    assert h.inspector.get_roi() == RegionOfInterest(
        x_min=0.0, x_max=100.0, y_min=0.0, y_max=80.0, z_min=0.0, z_max=40.0
    )
    assert h.model.get_roi_params() == RoiConfig()
    assert h.model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert h.model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE
    assert h.model.get_roi_params().frame_range is None


def test_undo_roi_restores_previous_crop_and_full_volume_in_model(qtbot) -> None:
    h = _make_harness(qtbot)
    roi_1 = RegionOfInterest(x_min=10.0, x_max=60.0, y_min=10.0, y_max=50.0, z_min=5.0, z_max=30.0)
    roi_2 = RegionOfInterest(x_min=20.0, x_max=40.0, y_min=15.0, y_max=35.0, z_min=10.0, z_max=20.0)

    _accept_bounds(h, roi_1)
    _accept_bounds(h, roi_2)
    h.pipeline.complete_stage(PipelineStep.PREPROCESSING)
    assert h.controller.has_undo

    undo_btn = h.inspector.findChild(QPushButton, names.ROI_INSPECTOR_UNDO_BUTTON)
    assert undo_btn is not None

    # First undo restores roi_1 and invalidates downstream stages
    undo_btn.click()
    assert h.vol.roi == roi_1
    assert h.model.get_roi_params().region == roi_1
    assert h.model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE
    assert h.controller.has_undo

    # Second undo restores full volume and clears PipelineStep.ROI params/status
    undo_btn.click()
    assert h.vol.roi is None
    assert not h.controller.has_undo
    assert h.model.get_roi_params().region is None
    assert h.model.get_status(PipelineStep.ROI) == StepStatus.IDLE


def test_select_roi_and_viewport_update_workflow(qtbot) -> None:
    h = _make_harness(qtbot)
    select_btn = h.inspector.findChild(QPushButton, names.ROI_INSPECTOR_SELECT_BUTTON)
    assert select_btn is not None

    select_btn.click()
    assert h.roi_view.started == 1
    assert not h.playback_bar.isEnabled()

    drawn_roi = RegionOfInterest(x_min=5.0, x_max=45.0, y_min=5.0, y_max=35.0, z_min=2.0, z_max=18.0)
    h.roi_view.roi_updated.emit(drawn_roi)
    h.roi_view.pending_accept_roi = drawn_roi
    assert h.inspector.get_roi() == drawn_roi

    accept_btn = h.inspector.findChild(QPushButton, names.ROI_INSPECTOR_ACCEPT_BUTTON)
    assert accept_btn is not None
    accept_btn.click()

    assert h.vol.roi == drawn_roi
    assert h.model.get_roi_params().region == drawn_roi
    assert h.model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert h.playback_bar.isEnabled()


def test_roi_actions_ignored_when_no_source_loaded(qtbot) -> None:
    h = _make_harness(qtbot, with_source=False)
    h.controller._on_start_roi_selection()
    h.controller._on_inspector_bounds_edited(
        RegionOfInterest(x_min=1.0, x_max=5.0, y_min=1.0, y_max=5.0, z_min=1.0, z_max=5.0)
    )
    assert h.roi_view.started == 0
    assert h.roi_view.previews == []
    assert isinstance(h.playback_bar, QWidget)


def test_run_up_to_roi_commits_full_volume_and_active_crop(qtbot) -> None:
    """Running Stage 1 without interactive box selection commits full volume or active crop."""
    h = _make_harness(qtbot)
    assert h.vol.roi is None

    h.pipeline.run_up_to(PipelineStep.ROI)

    assert h.model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert h.model.get_roi_params().region is None
    assert h.vol.roi is None

    crop = RegionOfInterest(x_min=5.0, x_max=45.0, y_min=5.0, y_max=35.0, z_min=2.0, z_max=18.0)
    _accept_bounds(h, crop)
    h.pipeline.reset_pipeline()
    h.pipeline.run_up_to(PipelineStep.ROI)

    assert h.model.get_status(PipelineStep.ROI) == StepStatus.COMPLETED
    assert h.model.get_roi_params().region == crop


def test_selected_frames_are_propagated_to_model_and_playback(qtbot, monkeypatch):
    h = _make_harness(qtbot)
    selected_range = FrameRange(1, 3)

    set_frame_range = MagicMock()
    monkeypatch.setattr(h.playback, "set_frame_range", set_frame_range)

    with qtbot.waitSignal(h.inspector.selected_frames_changed) as changed:
        h.inspector.frames_selector.selected_frames_changed.emit(selected_range)

    assert changed.args == [selected_range]
    assert h.model.get_roi_params().frame_range == selected_range

    set_frame_range.assert_called_once_with(selected_range)


def test_frame_range_update_preserves_existing_roi(qtbot) -> None:
    h = _make_harness(qtbot)

    accepted_roi = RegionOfInterest(
        x_min=10.0,
        x_max=50.0,
        y_min=10.0,
        y_max=40.0,
        z_min=5.0,
        z_max=25.0,
    )
    _accept_bounds(h, accepted_roi)

    selected_range = FrameRange(1, 3)
    h.inspector.frames_selector.selected_frames_changed.emit(selected_range)

    params = h.model.get_roi_params()

    assert params.region == accepted_roi
    assert params.frame_range == selected_range


def test_accepting_roi_preserves_selected_frame_range(qtbot) -> None:
    h = _make_harness(qtbot)

    selected_range = FrameRange(1, 3)
    h.inspector.frames_selector.selected_frames_changed.emit(selected_range)

    accepted_roi = RegionOfInterest(
        x_min=10.0,
        x_max=50.0,
        y_min=10.0,
        y_max=40.0,
        z_min=5.0,
        z_max=25.0,
    )
    _accept_bounds(h, accepted_roi)

    params = h.model.get_roi_params()

    assert params.region == accepted_roi
    assert params.frame_range == selected_range


def test_set_enabled_state_updates_frames_selector(qtbot, monkeypatch) -> None:
    h = _make_harness(qtbot)

    disable = MagicMock()
    monkeypatch.setattr(h.inspector.frames_selector, "disable", disable)

    h.inspector.set_enabled_state(False)
    h.inspector.set_enabled_state(True)

    assert [call.args for call in disable.call_args_list] == [
        (True,),
        (False,),
    ]
