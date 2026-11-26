"""Integration tests for detection and tracking."""

from pathlib import Path
from threading import Event
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
from PySide6.QtGui import QAction

from apkit4d.core.models import DetectionConfig
from apkit4d.gui.constants import names, texts
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.trajectory_detection import DetectionData
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziInfo, CziSource
from apkit4d.tracking.linker import ParticleLinker


def _controller(qtbot, qapp):
    window = MainWindow()
    qtbot.addWidget(window)

    controller = MainController(window, qapp)
    source = MagicMock(spec=CziSource)

    controller.file_controller._source = source
    controller.pipeline_controller.complete_stage(PipelineStep.ROI)
    controller.pipeline_controller.complete_stage(PipelineStep.PREPROCESSING)

    return controller, source


def _detections():
    return pd.DataFrame(
        {
            "frame": list(range(8)),
            "z_um": [0.0] * 8,
            "y_um": [0.0] * 8,
            "x_um": [float(i) for i in range(8)],
        }
    )


def test_detection_feeds_tracking_without_recalculation(qtbot, qapp, monkeypatch):
    controller, source = _controller(qtbot, qapp)
    calls = []
    detections = _detections()

    def fake_detect(czi, preproc, blob, roi):
        calls.append((czi, preproc, blob, roi))
        return DetectionData(
            detections,
            0.5,
            {"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        fake_detect,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert len(calls) == 1
    assert calls[0][0] is source
    assert calls[0][2] == DetectionConfig()
    assert calls[0][3] is None

    pd.testing.assert_frame_equal(
        controller.pipeline_model.batch_results[0],
        detections,
    )

    assert controller.tracking_result.metadata["num_detections"] == 8

    # Tracking parameters change, but detection must not rerun.
    controller.pipeline_model.update_step_params(
        PipelineStep.TRACKING,
        min_len=7,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert len(calls) == 1
    assert controller.tracking_result.metadata["num_detections"] == 8


def test_detection_failure_stops_pipeline(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)

    def fake_detect(*args, **kwargs):
        raise RuntimeError("Detection failed in test")

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        fake_detect,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE,
        timeout=10000,
    )

    assert controller.pipeline_model.batch_results is None
    assert controller.tracking_result is None

    assert "Detection failed in test" in (controller._window.right_panel.bottom_stats.details_label.text())


def test_detection_ignores_result_after_reset(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)
    started, release = Event(), Event()

    def fake_detect(*args, **kwargs):
        started.set()

        if not release.wait(timeout=10):
            raise TimeoutError("Detection test timed out")

        return DetectionData(
            _detections(),
            0.5,
            {"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        fake_detect,
    )

    try:
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

        qtbot.waitUntil(
            started.is_set,
            timeout=5000,
        )

        controller.pipeline_controller.reset_pipeline()

    finally:
        release.set()

    qtbot.waitUntil(
        lambda: controller.blob_controller is not None and controller.blob_controller._detection_task is None,
        timeout=10000,
    )

    assert controller.pipeline_model.batch_results is None
    assert controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE


def test_detection_reuses_stored_results(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)

    controller.pipeline_model.set_batch_results(
        _detections(),
        {"info": {"dt_s": 0.5}},
    )

    def forbidden(*args, **kwargs):
        raise AssertionError("Sequence detection was run again")

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        forbidden,
    )

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert controller.tracking_result.metadata["num_detections"] == 8


def test_detection_restarts_when_parameters_change(qtbot, qapp, monkeypatch):
    controller, _source = _controller(qtbot, qapp)
    started, release = Event(), Event()
    thresholds = []

    def fake_detect(czi, preproc, blob, roi):
        thresholds.append(blob.threshold)

        if len(thresholds) == 1:
            started.set()
            if not release.wait(timeout=10):
                raise TimeoutError("Detection test timed out")

        return DetectionData(
            _detections(),
            0.5,
            {"info": {"dt_s": 0.5}},
        )

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        fake_detect,
    )

    try:
        controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

        qtbot.waitUntil(
            started.is_set,
            timeout=5000,
        )

        controller.pipeline_model.update_step_params(
            PipelineStep.DETECTION,
            threshold=0.6,
        )

    finally:
        release.set()

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert thresholds == [DetectionConfig().threshold, 0.6]
    assert controller.tracking_result.metadata["num_detections"] == 8


def test_stage_3_completion_displays_blobs_across_frames_in_3d_view(qtbot, qapp, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    view = MagicMock()
    controller = MainController(window, qapp, view=view)

    source = MagicMock(spec=CziSource)
    source.info = CziInfo(
        path="sample.czi",
        n_t=3,
        n_z=4,
        n_y=6,
        n_x=6,
        n_c=1,
        dtype="uint16",
        px_size_x=1.0,
        px_size_y=1.0,
        px_size_z=1.0,
        dt_s=0.5,
        dt_source="test",
    )
    source.read.return_value = np.zeros((4, 6, 6), dtype=np.uint16)

    controller.file_controller._source = source
    window.set_current_file(Path("sample.czi"))
    controller.playback_controller.set_frame_count(3)
    assert controller.volume_controller is not None
    controller.volume_controller.set_source(Path("sample.czi"), source)
    qtbot.waitUntil(lambda: view.show_volume.called, timeout=5000)
    view.show_blobs.reset_mock()

    detections = pd.DataFrame(
        {
            "frame": [0, 2, 2],
            "z_um": [1.0, 2.0, 3.0],
            "y_um": [1.0, 2.0, 3.0],
            "x_um": [1.0, 2.0, 3.0],
            "volume_um3": [100.0, 200.0, 300.0],
            "response": [0.25, 0.5, 0.75],
        }
    )
    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        lambda *_args, **_kwargs: DetectionData(detections, 0.5, {"info": {"dt_s": 0.5}}),
    )

    controller.pipeline_controller.complete_stage(PipelineStep.ROI)
    controller.pipeline_controller.complete_stage(PipelineStep.PREPROCESSING)
    controller.pipeline_controller.run_up_to(PipelineStep.DETECTION)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED,
        timeout=10000,
    )
    assert view.show_blobs.called
    assert view.show_blobs.call_args.args[0].n_points == 1
    volume_action = window.findChild(QAction, names.SHOW_VOLUME_ACTION)
    assert volume_action is not None
    assert not volume_action.isChecked()
    view.set_volume_visible.assert_called_with(False)

    seed_hist = window.left_panel.histograms_section.seed_response_histogram
    assert np.allclose(seed_hist.seeds_response, [0.25])
    assert "1 " in seed_hist.plotItem.titleLabel.text

    view.show_blobs.reset_mock()
    controller.playback_controller.go_to_frame(2)
    qtbot.waitUntil(lambda: view.show_blobs.called, timeout=5000)
    assert view.show_blobs.call_args.args[0].n_points == 2
    assert np.allclose(seed_hist.seeds_response, [0.5, 0.75])
    assert "2 " in seed_hist.plotItem.titleLabel.text


def test_one_click_run_up_to_tracking_from_idle_auto_commits_config_stages(qtbot, qapp, monkeypatch):
    """Clicking Play on Tracking from IDLE must auto-commit ROI & Preprocessing without hanging."""
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    source = MagicMock(spec=CziSource)
    controller.file_controller._source = source

    detections = _detections()
    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        lambda *_args, **_kwargs: DetectionData(detections, 0.5, {"info": {"dt_s": 0.5}}),
    )

    assert controller.pipeline_model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert controller.pipeline_model.get_status(PipelineStep.PREPROCESSING) == StepStatus.IDLE

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )

    for step in (
        PipelineStep.ROI,
        PipelineStep.PREPROCESSING,
        PipelineStep.DETECTION,
        PipelineStep.TRACKING,
    ):
        assert controller.pipeline_model.get_status(step) == StepStatus.COMPLETED
    assert controller.tracking_result is not None
    assert controller.tracking_result.metadata["num_detections"] == 8
    assert controller._window.right_panel.bottom_stats.progress.isHidden()


def test_stage_3_detection_reports_frame_progress_and_hides_bar(qtbot, qapp, monkeypatch):
    """Detection stage emits frame progress with remaining frames and hides progress once done."""
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    source = MagicMock(spec=CziSource)
    source.info = CziInfo("sample.czi", 10, 4, 8, 8, 1, "uint16", 1.0, 1.0, 1.0, 0.5, "test")
    controller.file_controller._source = source

    observed_summaries: list[str] = []
    observed_details: list[str] = []
    observed_values: list[int] = []

    def fake_detect(czi, preproc, blob, roi=None, *, progress_callback=None):
        assert progress_callback is not None
        progress_callback(4, 10)
        return DetectionData(_detections(), 0.5, {"info": {"dt_s": 0.5}})

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        fake_detect,
    )

    stats = window.right_panel.bottom_stats
    original_report = controller.pipeline_controller.report_stage_progress

    def spy_report(*args, **kwargs):
        original_report(*args, **kwargs)
        observed_summaries.append(stats.summary_label.text())
        observed_details.append(stats.details_label.text())
        observed_values.append(stats.progress.value())

    monkeypatch.setattr(controller.pipeline_controller, "report_stage_progress", spy_report)

    controller.pipeline_controller.run_up_to(PipelineStep.DETECTION)

    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED,
        timeout=10000,
    )

    assert any("4/10 frames" in s for s in observed_summaries)
    assert any("6 remaining" in d for d in observed_details)
    assert 4 in observed_values
    assert stats.progress.isHidden()


def test_normalization_off_blocks_detection_and_queued_tracking(qtbot, qapp, monkeypatch):
    """Disabling normalization blocks pipeline detection, queued tracking, and stage play buttons."""
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    source = MagicMock(spec=CziSource)
    source.channel = 0
    source.info = CziInfo("sample.czi", 4, 4, 8, 8, 1, "uint16", 1.0, 1.0, 1.0, 0.5, "test")
    controller.file_controller._source = source
    controller.file_controller.loaded.emit(Path("sample.czi"), source)

    def forbidden_detect(*_args, **_kwargs):
        raise AssertionError("Detection must not run while normalization is disabled")

    def forbidden_link(*_args, **_kwargs):
        raise AssertionError("Tracking must not run while normalization is disabled")

    monkeypatch.setattr("apkit4d.gui.controllers.blob_detection_controller.detect_sequence", forbidden_detect)
    monkeypatch.setattr(ParticleLinker, "link", forbidden_link)

    controller.pipeline_model.update_step_params(PipelineStep.PREPROCESSING, normalization_enabled=False)

    panel = window.right_panel
    for step in (PipelineStep.DETECTION, PipelineStep.TRACKING, PipelineStep.BATCH):
        btn = panel.get_play_button(step)
        assert btn is not None and not btn.isEnabled()
        assert btn.toolTip() == texts.DETECTION_REQUIRES_NORMALIZATION

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    assert controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE
    assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert panel.bottom_stats.summary_label.text() == texts.STATS_DETECTION_BLOCKED_SUMMARY
    assert texts.DETECTION_REQUIRES_NORMALIZATION in panel.bottom_stats.details_label.text()

    # Defense-in-depth: even if DETECTION & TRACKING are queued manually via the model, abort cleanly
    controller.pipeline_controller.complete_stage(PipelineStep.ROI)
    controller.pipeline_controller.complete_stage(PipelineStep.PREPROCESSING)
    controller.pipeline_model.plan_execution(PipelineStep.DETECTION, PipelineStep.TRACKING)
    controller.pipeline_model.set_step_status(PipelineStep.DETECTION, StepStatus.RUNNING)

    assert controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE
    assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
    assert controller.pipeline_model.batch_results is None

    # Re-enabling normalization restores play buttons and allows detection -> tracking
    detections = _detections()
    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        lambda *_args, **_kwargs: DetectionData(detections, 0.5, {"info": {"dt_s": 0.5}}),
    )
    monkeypatch.undo()
    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        lambda *_args, **_kwargs: DetectionData(detections, 0.5, {"info": {"dt_s": 0.5}}),
    )

    controller.pipeline_model.update_step_params(PipelineStep.PREPROCESSING, normalization_enabled=True)
    for step in (PipelineStep.DETECTION, PipelineStep.TRACKING, PipelineStep.BATCH):
        btn = panel.get_play_button(step)
        assert btn is not None and btn.isEnabled()
        assert btn.toolTip() == texts.TOOLTIP_PLAY_STAGE

    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)
    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED,
        timeout=10000,
    )
    assert controller.tracking_result is not None


def test_turning_normalization_off_after_detection_invalidates_stale_tracking(qtbot, qapp, monkeypatch):
    """Turning normalization off after Stage 3 prevents queued tracking on invalidated data."""
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp)

    source = MagicMock(spec=CziSource)
    source.channel = 0
    source.info = CziInfo("sample.czi", 4, 4, 8, 8, 1, "uint16", 1.0, 1.0, 1.0, 0.5, "test")
    controller.file_controller._source = source
    controller.file_controller.loaded.emit(Path("sample.czi"), source)

    monkeypatch.setattr(
        "apkit4d.gui.controllers.blob_detection_controller.detect_sequence",
        lambda *_args, **_kwargs: DetectionData(_detections(), 0.5, {"info": {"dt_s": 0.5}}),
    )
    controller.pipeline_controller.run_up_to(PipelineStep.DETECTION)
    qtbot.waitUntil(
        lambda: controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.COMPLETED,
        timeout=10000,
    )
    assert controller.pipeline_model.batch_results is not None

    monkeypatch.setattr(
        ParticleLinker,
        "link",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("Tracking must not execute")),
    )
    controller.pipeline_model.update_step_params(PipelineStep.PREPROCESSING, normalization_enabled=False)
    controller.pipeline_controller.run_up_to(PipelineStep.TRACKING)

    assert controller.pipeline_model.batch_results is None
    assert controller.pipeline_model.get_status(PipelineStep.DETECTION) == StepStatus.IDLE
    assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.IDLE
