import threading
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PySide6.QtCore import Qt

from apkit4d.detection.blob_detection import BlobParams
from apkit4d.gui.controllers import blob_detection_controller as module
from apkit4d.gui.controllers.blob_detection_controller import (
    BlobDetection,
    BlobDetectionController,
)
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.trajectory_detection import DetectionData
from apkit4d.gui.controllers.volume_controller import PreparedVolume
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep, StepStatus
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.stages.blob_detection_inspector import BlobDetectionInspector

BLOBS = pd.DataFrame(
    {
        "x_um": [1.0],
        "y_um": [2.0],
        "z_um": [3.0],
        "volume_um3": [500.0],
    }
)
SOURCE = types.SimpleNamespace(info=types.SimpleNamespace(voxel=(1, 1, 1)))


class FakeView:
    def __init__(self):
        self.meshes = []

    def show_blobs(self, poly):
        self.meshes.append(poly)


def make_prepared(frame: int = 0, *, is_image_normalized: bool = True) -> PreparedVolume:
    """A new volume every time: the controller tells volumes apart by identity."""
    return PreparedVolume(
        is_image_normalized=is_image_normalized,
        frame=frame,
        voxel=(1.0, 1.0, 1.0),
        roi_volume=np.zeros((2, 3, 4), dtype=np.uint16),
        image=np.zeros((2, 3, 4), dtype=np.float32),
        offset=(0, 0, 0),
    )


@pytest.fixture
def fake_detect(monkeypatch):
    recorded = []  # (prepared volume, params) of every detection

    def fake(prepared, params):
        recorded.append((prepared, params))
        return BlobDetection(prepared.frame, BLOBS.copy())

    monkeypatch.setattr(module, "detect_blobs", fake)

    return recorded


@pytest.fixture
def blocking_detect(fake_detect, monkeypatch):
    """Detections that start and end only when the test releases them. Replaces `fake_detect`."""

    release = threading.Event()
    started = []

    def fake(prepared, params):
        started.append((prepared, params))
        release.wait(2)
        return BlobDetection(prepared.frame, BLOBS.copy())

    monkeypatch.setattr(module, "detect_blobs", fake)

    yield types.SimpleNamespace(started=started, release=release)

    release.set()  # never leave a worker thread blocked


@pytest.fixture
def setup(qtbot, fake_detect):
    inspector = BlobDetectionInspector()
    qtbot.addWidget(inspector)

    view = FakeView()
    controller = BlobDetectionController(inspector, view)

    controller.set_source(Path("sample.czi"), SOURCE)

    # set_source clears the view once.
    view.meshes.clear()

    return inspector, view, controller


def announce(setup, frame: int = 0, *, is_image_normalized: bool = True) -> PreparedVolume:
    """The 3D view shows a new volume and announces it to the controller."""

    _, view, controller = setup
    prepared = make_prepared(frame, is_image_normalized=is_image_normalized)
    controller.on_volume_prepared(prepared)
    view.meshes.clear()
    return prepared


def click_find_blobs(qtbot, inspector):
    qtbot.mouseClick(inspector._find_blobs_button, Qt.MouseButton.LeftButton)


def enable_update_on_change(inspector):
    """Tick the checkbox without the detection its signal would schedule."""

    inspector._update_on_change.blockSignals(True)
    inspector._update_on_change.setChecked(True)
    inspector._update_on_change.blockSignals(False)


def test_find_blobs_detects_the_volume_on_screen_and_shows_the_result(qtbot, setup, fake_detect):
    inspector, view, _ = setup
    prepared = announce(setup, frame=2)

    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(view.meshes) == 1)

    assert len(fake_detect) == 1
    assert fake_detect[0][0] is prepared
    assert view.meshes[0].n_points == 1


def test_find_blobs_does_nothing_without_a_volume(qtbot, setup, fake_detect):
    inspector, view, _ = setup
    click_find_blobs(qtbot, inspector)
    qtbot.wait(100)
    assert fake_detect == []
    assert view.meshes == []


def test_find_blobs_does_nothing_when_volume_is_not_normalized(qtbot, setup, fake_detect):
    inspector, view, _ = setup
    prepared = announce(setup, is_image_normalized=False)
    click_find_blobs(qtbot, inspector)
    qtbot.wait(100)
    assert prepared.is_image_normalized is False
    assert fake_detect == []
    assert view.meshes == []


def test_detection_works_again_when_a_normalized_volume_arrives(qtbot, setup, fake_detect):
    inspector, view, _ = setup
    announce(setup, frame=0, is_image_normalized=False)
    click_find_blobs(qtbot, inspector)
    qtbot.wait(100)
    assert fake_detect == []

    normalized = announce(setup, frame=1, is_image_normalized=True)
    click_find_blobs(qtbot, inspector)
    qtbot.waitUntil(lambda: len(view.meshes) == 1)

    assert len(fake_detect) == 1
    assert fake_detect[0][0] is normalized
    assert view.meshes[0].n_points == 1


def test_update_on_change_does_not_detect_an_unnormalized_volume(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    enable_update_on_change(inspector)
    announce(setup, is_image_normalized=False)
    inspector._lo_g_threshold.setValue(0.3)
    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 100)
    assert fake_detect == []


def test_normalization_toggle_disables_detection_controls_and_resets_live_update(
    setup,
):
    inspector, _, controller = setup
    enable_update_on_change(inspector)
    controller.on_normalization_toggled(False)
    assert inspector._find_blobs_button.isEnabled() is False
    assert inspector._update_on_change.isEnabled() is False
    assert inspector.update_on_change is False
    controller.on_normalization_toggled(True)
    assert inspector._find_blobs_button.isEnabled() is True
    assert inspector._update_on_change.isEnabled() is True
    assert inspector.update_on_change is False


def test_find_blobs_uses_the_latest_volume(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    announce(setup, frame=0)
    latest = announce(setup, frame=3)

    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(fake_detect) == 1)
    assert fake_detect[0][0] is latest


def test_a_new_volume_clears_the_blobs_on_screen(qtbot, setup):
    inspector, view, controller = setup
    announce(setup)
    click_find_blobs(qtbot, inspector)
    qtbot.waitUntil(lambda: len(view.meshes) == 1)

    controller.on_volume_prepared(make_prepared(1))

    assert view.meshes[-1].n_points == 0


def test_without_update_on_change_a_new_volume_is_not_detected(qtbot, setup, fake_detect):
    announce(setup, frame=0)
    announce(setup, frame=1)

    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 200)

    assert fake_detect == []


def test_update_on_change_detects_each_new_volume(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    enable_update_on_change(inspector)

    announce(setup, frame=0)
    qtbot.waitUntil(lambda: len(fake_detect) == 1)
    announce(setup, frame=1)
    qtbot.waitUntil(lambda: len(fake_detect) == 2)

    assert [prepared.frame for prepared, _ in fake_detect] == [0, 1]


def test_the_same_volume_announced_twice_changes_nothing(qtbot, setup, fake_detect):
    inspector, view, controller = setup
    enable_update_on_change(inspector)
    prepared = make_prepared(0)

    controller.on_volume_prepared(prepared)
    qtbot.waitUntil(lambda: len(view.meshes) > 0 and view.meshes[-1].n_points == 1)
    shown = len(view.meshes)
    controller.on_volume_prepared(prepared)
    qtbot.wait(100)
    assert len(view.meshes) == shown
    assert len(fake_detect) == 1


def test_a_result_for_a_replaced_volume_is_discarded(qtbot, setup, blocking_detect):
    inspector, view, _ = setup
    announce(setup, frame=0)
    click_find_blobs(qtbot, inspector)
    qtbot.waitUntil(lambda: len(blocking_detect.started) == 1)
    announce(setup, frame=1)
    blocking_detect.release.set()
    qtbot.wait(300)

    assert view.meshes == []
    assert len(blocking_detect.started) == 1


def test_volumes_arriving_during_a_detection_detect_only_the_latest(qtbot, setup, blocking_detect):
    inspector, view, _ = setup
    enable_update_on_change(inspector)
    announce(setup, frame=1)
    qtbot.waitUntil(lambda: len(blocking_detect.started) == 1)
    announce(setup, frame=2)
    announce(setup, frame=3)
    blocking_detect.release.set()
    qtbot.waitUntil(lambda: len(blocking_detect.started) == 2)
    qtbot.waitUntil(lambda: len(view.meshes) == 1)
    qtbot.wait(100)
    assert [prepared.frame for prepared, _ in blocking_detect.started] == [1, 3]
    assert len(view.meshes) == 1


def test_a_result_computed_with_old_parameters_is_discarded(qtbot, setup, blocking_detect):
    inspector, view, _ = setup
    enable_update_on_change(inspector)
    announce(setup)
    qtbot.waitUntil(lambda: len(blocking_detect.started) == 1)

    inspector._lo_g_threshold.setValue(0.3)
    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 200)
    blocking_detect.release.set()

    qtbot.waitUntil(lambda: len(blocking_detect.started) == 2)
    qtbot.waitUntil(lambda: len(view.meshes) == 1)
    assert blocking_detect.started[1][1].threshold == 0.3


@pytest.mark.parametrize(
    "close",
    [
        pytest.param(lambda controller: controller.clear_source(), id="clear_source"),
        pytest.param(
            lambda controller: controller.set_source(Path("other.czi"), SOURCE),
            id="set_source",
        ),
    ],
)
def test_closing_the_recording_forgets_the_volume(qtbot, setup, fake_detect, close):
    inspector, view, controller = setup
    announce(setup)

    close(controller)
    click_find_blobs(qtbot, inspector)
    qtbot.wait(100)

    assert view.meshes[-1].n_points == 0
    assert fake_detect == []


def test_parameter_change_does_not_run_without_update_on_change(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    announce(setup)
    inspector._lo_g_threshold.setValue(0.3)

    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 200)

    assert fake_detect == []


def test_update_on_change_runs_once_for_several_changes(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    announce(setup)

    inspector._update_on_change.setChecked(True)
    inspector._lo_g_threshold.setValue(0.2)
    inspector._lo_g_threshold.setValue(0.3)

    qtbot.waitUntil(lambda: len(fake_detect) >= 1)
    qtbot.wait(BlobDetectionController.DEBOUNCE_MS + 200)

    assert len(fake_detect) == 1
    assert fake_detect[0][1].threshold == 0.3


def test_z_equals_xy_is_synchronized_by_the_view(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    announce(setup)

    inspector._diameter_z_equals_xy.setChecked(True)
    inspector._diameter_xy.setValue(16.0)
    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(fake_detect) == 1)
    params = fake_detect[0][1]

    assert params.diameter_xy_um == 16.0
    assert params.diameter_z_um == 16.0


def test_xy_and_z_can_differ_when_checkbox_is_unchecked(qtbot, setup, fake_detect):
    inspector, _, _ = setup
    announce(setup)

    inspector._diameter_z_equals_xy.setChecked(False)
    inspector._diameter_xy.setValue(16.0)
    inspector._diameter_z.setValue(70.0)
    click_find_blobs(qtbot, inspector)

    qtbot.waitUntil(lambda: len(fake_detect) == 1)
    params = fake_detect[0][1]

    assert params.diameter_xy_um == 16.0
    assert params.diameter_z_um == 70.0


def test_detect_blobs_runs_find_blobs_on_the_prepared_volume(monkeypatch):
    prepared = PreparedVolume(
        is_image_normalized=True,
        frame=3,
        voxel=(5.0, 1.0, 2.0),
        roi_volume=np.ones((2, 3, 4), dtype=np.uint16),
        image=np.zeros((2, 3, 4), dtype=np.float32),
        offset=(1, 2, 3),
    )
    params = BlobParams()
    seen = {}

    def fake_find_blobs(image, p, voxel_dim, **kwargs):
        seen.update(image=image, params=p, voxel=voxel_dim, kwargs=kwargs)
        return (BLOBS.copy(), None, np.array([]))

    monkeypatch.setattr("apkit4d.pipeline.frame_stages.find_blobs", fake_find_blobs)

    result = module.detect_blobs(prepared, params)
    assert seen["image"] is prepared.image
    assert seen["params"] is params
    assert seen["voxel"] == (5.0, 1.0, 2.0)
    assert seen["kwargs"]["intensity"] is prepared.roi_volume
    assert seen["kwargs"]["offset"] == (1, 2, 3)
    assert seen["kwargs"]["frame"] == 3
    assert result.frame == 3
    assert len(result.blobs) == 1


def test_detect_blobs_rejects_unnormalized_prepared_volume():
    prepared = make_prepared(frame=0, is_image_normalized=False)
    with pytest.raises(ValueError, match="normalization must be enabled"):
        module.detect_blobs(prepared, BlobParams())


def test_precomputed_blobs_render_across_frames_without_detection(setup, fake_detect):
    _inspector, view, controller = setup
    precomputed = pd.DataFrame(
        {
            "frame": [0, 0, 3],
            "x_um": [1.0, 2.0, 4.0],
            "y_um": [2.0, 3.0, 5.0],
            "z_um": [3.0, 4.0, 6.0],
            "volume_um3": [500.0, 600.0, 700.0],
        }
    )

    controller.set_precomputed_blobs(precomputed)
    assert view.meshes[-1].n_points == 2

    controller.on_volume_prepared(make_prepared(3))
    assert view.meshes[-1].n_points == 1

    controller.on_volume_prepared(make_prepared(4))
    assert view.meshes[-1].n_points == 0

    controller.set_precomputed_blobs(None)
    assert view.meshes[-1].n_points == 0
    assert fake_detect == []


SEEDS = np.array([0.05, 0.2, 0.4], dtype=np.float32)


def test_the_response_of_the_candidates_is_announced(qtbot, setup, monkeypatch) -> None:
    inspector, _, controller = setup
    monkeypatch.setattr(
        module, "detect_blobs", lambda prepared, params: BlobDetection(prepared.frame, BLOBS.copy(), SEEDS)
    )
    announce(setup)

    with qtbot.waitSignal(controller.seeds_response_changed) as blocker:
        click_find_blobs(qtbot, inspector)

    assert np.array_equal(blocker.args[0], SEEDS)


def test_the_response_is_announced_even_when_no_blob_is_found(qtbot, setup, monkeypatch) -> None:
    inspector, _, controller = setup
    monkeypatch.setattr(
        module, "detect_blobs", lambda prepared, params: BlobDetection(prepared.frame, pd.DataFrame(), SEEDS)
    )
    announce(setup)

    with qtbot.waitSignal(controller.seeds_response_changed) as blocker:
        click_find_blobs(qtbot, inspector)

    assert np.array_equal(blocker.args[0], SEEDS)


@pytest.mark.parametrize(
    "close",
    [
        pytest.param(lambda controller: controller.clear_source(), id="clear_source"),
        pytest.param(lambda controller: controller.set_source(Path("other.czi"), SOURCE), id="set_source"),
    ],
)
def test_closing_the_recording_empties_the_histogram(qtbot, setup, close) -> None:
    _, _, controller = setup

    with qtbot.waitSignal(controller.seeds_response_changed) as blocker:
        close(controller)

    assert blocker.args == [None]


def test_pipeline_model_detection_params_sync_controller_and_inspector(qtbot) -> None:
    right_panel = RightPanel()
    qtbot.addWidget(right_panel)
    inspector = right_panel.detection_inspector
    assert inspector is not None

    model = PipelineModel()
    pipeline = PipelineController(model, right_panel)
    view = FakeView()
    controller = BlobDetectionController(
        inspector,
        view,
        pipeline_model=model,
        pipeline_controller=pipeline,
    )

    model.update_step_params(PipelineStep.DETECTION, threshold=0.42, min_volume_um3=333.0)
    assert controller.params.threshold == pytest.approx(0.42)
    assert controller.params.min_volume_um3 == pytest.approx(333.0)
    assert inspector.lo_g_threshold == pytest.approx(0.42)
    assert inspector.min_volume == pytest.approx(333.0)

    model.reset_step_params(PipelineStep.DETECTION)
    assert controller.params == BlobParams()
    assert inspector.get_params() == BlobParams()


def test_stage_3_sequence_detection_populates_precomputed_blobs_for_playback(qtbot, monkeypatch) -> None:
    right_panel = RightPanel()
    qtbot.addWidget(right_panel)
    inspector = right_panel.detection_inspector
    assert inspector is not None

    model = PipelineModel()
    pipeline = PipelineController(model, right_panel)
    file_controller = types.SimpleNamespace(source=SOURCE)
    view = FakeView()
    controller = BlobDetectionController(
        inspector,
        view,
        pipeline_model=model,
        pipeline_controller=pipeline,
        file_controller=file_controller,  # type: ignore[arg-type]
    )
    controller.on_volume_prepared(make_prepared(frame=0))
    view.meshes.clear()

    detections = pd.DataFrame(
        {
            "frame": [0, 2, 2],
            "x_um": [1.0, 4.0, 5.0],
            "y_um": [2.0, 5.0, 6.0],
            "z_um": [3.0, 6.0, 7.0],
            "volume_um3": [500.0, 600.0, 700.0],
            "response": [0.25, 0.4, 0.8],
        }
    )
    monkeypatch.setattr(
        module,
        "detect_sequence",
        lambda *_args, **_kwargs: DetectionData(detections, 0.5, {"info": {"dt_s": 0.5}}),
    )

    announced_responses: list[object] = []
    controller.seeds_response_changed.connect(announced_responses.append)

    pipeline.complete_stage(PipelineStep.ROI)
    pipeline.complete_stage(PipelineStep.PREPROCESSING)
    pipeline.run_up_to(PipelineStep.DETECTION)

    qtbot.waitUntil(
        lambda: model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED,
        timeout=5000,
    )

    # Frame 0 is shown immediately upon completion; scrubbing to frame 1 and 2 updates 3D view & histogram
    assert view.meshes[-1].n_points == 1
    assert np.allclose(announced_responses[-1], [0.25])

    controller.on_volume_prepared(make_prepared(frame=1))
    assert view.meshes[-1].n_points == 0
    assert len(announced_responses[-1]) == 0

    controller.on_volume_prepared(make_prepared(frame=2))
    assert view.meshes[-1].n_points == 2
    assert np.allclose(announced_responses[-1], [0.4, 0.8])
