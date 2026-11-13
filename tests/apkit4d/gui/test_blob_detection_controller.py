import types
from pathlib import Path

import pandas as pd
import pytest
from PySide6.QtCore import Qt

from apkit4d.gui.controllers.blob_detection_controller import (
    BlobDetectionController,
    _BlobDetection,
)
from apkit4d.gui.views.widgets.blob_detection_inspector import (
    BlobDetectionInspector,
)

BLOBS = pd.DataFrame(
    {
        "x_um": [1.0],
        "y_um": [2.0],
        "z_um": [3.0],
        "volume_um3": [500.0],
    }
)


class FakeView:
    def __init__(self):
        self.meshes = []

    def show_blobs(self, poly):
        self.meshes.append(poly)


@pytest.fixture
def fake_detect(monkeypatch):
    recorded = []

    def fake(self, source, frame, params):
        recorded.append((frame, params))
        return _BlobDetection(frame, BLOBS.copy())

    monkeypatch.setattr(
        BlobDetectionController,
        "_detect_blobs",
        fake,
    )

    return recorded


@pytest.fixture
def setup(qtbot, fake_detect):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    view = FakeView()
    controller = BlobDetectionController(inspector, view)

    source = types.SimpleNamespace(info=types.SimpleNamespace(voxel=(1, 1, 1)))

    controller.set_source(Path("sample.czi"), source)

    # set_source clears the view once.
    view.meshes.clear()

    return inspector, view, controller


def click_find_blobs(qtbot, inspector):
    qtbot.mouseClick(
        inspector._find_blobs_button,
        Qt.MouseButton.LeftButton,
    )


def test_find_blobs_runs_a_detection_and_shows_the_result(qtbot, setup, fake_detect):
    inspector, view, _ = setup

    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(view.meshes) == 1)

    assert len(fake_detect) == 1
    assert view.meshes[0].n_points == 1


def test_parameter_change_does_not_run_without_update_on_change(qtbot, setup, fake_detect):
    inspector, _, _ = setup

    inspector._lo_g_threshold.setValue(0.3)

    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 200)

    assert fake_detect == []


def test_update_on_change_runs_once_for_several_changes(qtbot, setup, fake_detect):
    inspector, _, _ = setup

    inspector._update_on_change.setChecked(True)
    inspector._lo_g_threshold.setValue(0.2)
    inspector._lo_g_threshold.setValue(0.3)

    qtbot.waitUntil(lambda: len(fake_detect) >= 1)
    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 200)

    assert len(fake_detect) == 1
    assert fake_detect[0][1].threshold == 0.3


def test_z_equals_xy_is_synchronized_by_the_view(qtbot, setup, fake_detect):
    inspector, _, _ = setup

    inspector._diameter_z_equals_xy.setChecked(True)

    # Changing XY while the checkbox is checked must also update Z.
    inspector._diameter_xy.setValue(16.0)

    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(fake_detect) == 1)

    params = fake_detect[0][1]

    assert params.diameter_xy_um == 16.0
    assert params.diameter_z_um == 16.0


def test_xy_and_z_can_differ_when_checkbox_is_unchecked(qtbot, setup, fake_detect):
    inspector, _, _ = setup

    inspector._diameter_z_equals_xy.setChecked(False)

    inspector._diameter_xy.setValue(16.0)
    inspector._diameter_z.setValue(70.0)

    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(fake_detect) == 1)

    params = fake_detect[0][1]

    assert params.diameter_xy_um == 16.0
    assert params.diameter_z_um == 70.0


def test_changing_frame_without_update_on_change_clears_the_blobs(qtbot, setup):
    inspector, view, controller = setup

    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(view.meshes) == 1)

    controller.on_set_frame(5)

    assert view.meshes[-1].n_points == 0
