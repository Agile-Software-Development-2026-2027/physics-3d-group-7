import numpy as np
import pytest
from PySide6.QtWidgets import QDoubleSpinBox, QLabel, QPushButton

from apkit4d.gui.constants import names, texts
from apkit4d.gui.models.pipeline_model import PipelineStep
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.widgets.roi_inspector import RoiInspector
from apkit4d.roi import RegionOfInterest


@pytest.fixture
def inspector(qtbot) -> RoiInspector:
    widget = RoiInspector()
    qtbot.addWidget(widget)
    return widget


class TestRoiInspector:
    def test_widgets_exist_with_expected_object_names(self, inspector: RoiInspector):
        for spin_name in (
            names.ROI_INSPECTOR_X_MIN,
            names.ROI_INSPECTOR_X_MAX,
            names.ROI_INSPECTOR_Y_MIN,
            names.ROI_INSPECTOR_Y_MAX,
            names.ROI_INSPECTOR_Z_MIN,
            names.ROI_INSPECTOR_Z_MAX,
        ):
            assert inspector.findChild(QDoubleSpinBox, spin_name) is not None

        for btn_name in (
            names.ROI_INSPECTOR_SELECT_BUTTON,
            names.ROI_INSPECTOR_ACCEPT_BUTTON,
            names.ROI_INSPECTOR_CANCEL_BUTTON,
            names.ROI_INSPECTOR_RESET_BUTTON,
        ):
            assert inspector.findChild(QPushButton, btn_name) is not None

        status = inspector.findChild(QLabel, names.ROI_INSPECTOR_STATUS_LABEL)
        assert status is not None
        assert status.text() == texts.INSPECTOR_STATUS_ROI_FULL

    def test_initial_editing_mode_is_disabled(self, inspector: RoiInspector):
        accept_btn = inspector.findChild(QPushButton, names.ROI_INSPECTOR_ACCEPT_BUTTON)
        cancel_btn = inspector.findChild(QPushButton, names.ROI_INSPECTOR_CANCEL_BUTTON)
        select_btn = inspector.findChild(QPushButton, names.ROI_INSPECTOR_SELECT_BUTTON)
        reset_btn = inspector.findChild(QPushButton, names.ROI_INSPECTOR_RESET_BUTTON)

        assert not accept_btn.isEnabled()
        assert not cancel_btn.isEnabled()
        assert select_btn.isEnabled()
        assert reset_btn.isEnabled()

    def test_set_volume_bounds_configures_ranges_without_emitting_bounds_edited(
        self, inspector: RoiInspector
    ):
        edited_events: list[RegionOfInterest] = []
        inspector.bounds_edited.connect(edited_events.append)

        vol_bounds = (0.0, 100.0, 0.0, 80.0, 0.0, 40.0)
        inspector.set_volume_bounds(vol_bounds)

        assert edited_events == []
        np.testing.assert_allclose(inspector.get_roi().bounds, vol_bounds)

        x_max = inspector.findChild(QDoubleSpinBox, names.ROI_INSPECTOR_X_MAX)
        z_max = inspector.findChild(QDoubleSpinBox, names.ROI_INSPECTOR_Z_MAX)
        assert x_max.maximum() == pytest.approx(100.0)
        assert z_max.maximum() == pytest.approx(40.0)

    def test_set_roi_bounds_updates_spinboxes_silently(self, inspector: RoiInspector):
        inspector.set_volume_bounds((0.0, 100.0, 0.0, 100.0, 0.0, 50.0))

        edited_events: list[RegionOfInterest] = []
        inspector.bounds_edited.connect(edited_events.append)

        sub_bounds = (10.0, 50.0, 20.0, 60.0, 5.0, 25.0)
        inspector.set_roi_bounds(sub_bounds)

        assert edited_events == []
        np.testing.assert_allclose(inspector.get_roi().bounds, sub_bounds)

    def test_manual_spinbox_edit_emits_bounds_edited_and_enables_editing_mode(self, inspector: RoiInspector):
        inspector.set_volume_bounds((0.0, 100.0, 0.0, 100.0, 0.0, 50.0))

        edited_events: list[RegionOfInterest] = []
        inspector.bounds_edited.connect(edited_events.append)

        x_min = inspector.findChild(QDoubleSpinBox, names.ROI_INSPECTOR_X_MIN)
        x_min.setValue(15.5)

        assert len(edited_events) == 1
        assert edited_events[0].x_min == pytest.approx(15.5)

        accept_btn = inspector.findChild(QPushButton, names.ROI_INSPECTOR_ACCEPT_BUTTON)
        cancel_btn = inspector.findChild(QPushButton, names.ROI_INSPECTOR_CANCEL_BUTTON)
        status = inspector.findChild(QLabel, names.ROI_INSPECTOR_STATUS_LABEL)
        assert accept_btn.isEnabled()
        assert cancel_btn.isEnabled()
        assert status.text() == texts.INSPECTOR_STATUS_ROI_SELECTING

    def test_buttons_emit_expected_signals(self, inspector: RoiInspector):
        inspector.set_editing_mode(True)

        select_clicks, accept_clicks, cancel_clicks, reset_clicks = [], [], [], []
        inspector.select_roi_clicked.connect(lambda: select_clicks.append(True))
        inspector.accept_roi_clicked.connect(lambda: accept_clicks.append(True))
        inspector.cancel_roi_clicked.connect(lambda: cancel_clicks.append(True))
        inspector.reset_roi_clicked.connect(lambda: reset_clicks.append(True))

        inspector.findChild(QPushButton, names.ROI_INSPECTOR_SELECT_BUTTON).click()
        inspector.findChild(QPushButton, names.ROI_INSPECTOR_ACCEPT_BUTTON).click()
        inspector.findChild(QPushButton, names.ROI_INSPECTOR_CANCEL_BUTTON).click()
        inspector.findChild(QPushButton, names.ROI_INSPECTOR_RESET_BUTTON).click()

        assert len(select_clicks) == 1
        assert len(accept_clicks) == 1
        assert len(cancel_clicks) == 1
        assert len(reset_clicks) == 1

    def test_set_status_text_updates_label(self, inspector: RoiInspector):
        inspector.set_status_text("Custom ROI status")
        status = inspector.findChild(QLabel, names.ROI_INSPECTOR_STATUS_LABEL)
        assert status.text() == "Custom ROI status"

    def test_right_panel_registers_roi_inspector_in_roi_stage(self, qtbot):
        panel = RightPanel()
        qtbot.addWidget(panel)

        assert panel.roi_inspector is not None
        roi_sec = panel.get_section(PipelineStep.ROI)
        assert roi_sec is not None
        assert roi_sec.findChild(RoiInspector, names.ROI_INSPECTOR_STEP) is panel.roi_inspector

        panel.clear_sections()
        assert panel.roi_inspector is None
