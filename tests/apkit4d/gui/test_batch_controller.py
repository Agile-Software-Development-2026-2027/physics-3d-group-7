"""Batch export must follow pipeline stages and save prepared data without recomputation."""

import json
from unittest.mock import MagicMock

import pandas as pd
import pytest
from PySide6.QtWidgets import QFileDialog

from apkit4d.gui.controllers.batch_controller import BatchController
from apkit4d.gui.controllers.file_controller import FileController
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziInfo, CziSource
from apkit4d.io.table import read_table


@pytest.fixture
def setup_batch(qtbot, tmp_path, monkeypatch):
    window = MainWindow()
    qtbot.addWidget(window)
    source = MagicMock(spec=CziSource)
    source.channel = 1
    source.info = CziInfo(str(tmp_path / "sample.czi"), 4, 10, 20, 20, 2, "uint16", 1, 1, 1, 0.5, "test")
    files = FileController(window, lambda _: source)
    pipeline = PipelineController(PipelineModel(window), window.right_panel, window)
    controller = BatchController(window, files, pipeline, window)
    with qtbot.waitSignal(files.loaded):
        files.open_file(tmp_path / "sample.czi")
    metadata = {
        "czi": str(tmp_path / "sample.czi"),
        "channel": 1,
        "t0": 0,
        "t1": 3,
        "info": {"dt_s": 0.5, "dt_source": "test"},
        "preproc": {},
        "blob": {"threshold": 0.2},
    }
    detections = pd.DataFrame(
        {"frame": [0, 1, 2, 3], "label": [7, 8, 9, 10], "t_s": [0.0, 0.5, 1.0, 1.5], "x_um": [1.25] * 4}
    )

    def no_recomputation(*args, **kwargs):
        raise AssertionError("Export must not rerun processing")

    monkeypatch.setattr("apkit4d.batching.processor.run_batch", no_recomputation)
    return window, controller, files, source, pipeline, detections, metadata


def complete_analysis(pipeline):
    for step in (PipelineStep.ROI, PipelineStep.PREPROCESSING, PipelineStep.DETECTION, PipelineStep.TRACKING):
        pipeline.complete_stage(step)


@pytest.mark.parametrize("fmt", ["csv", "parquet"])
@pytest.mark.parametrize("empty", [False, True])
def test_export_runs_only_when_pipeline_reaches_batch(setup_batch, qtbot, tmp_path, monkeypatch, fmt, empty):
    window, controller, files, source, pipeline, detections, metadata = setup_batch
    view = window.right_panel.batch_inspector
    assert view.output_dir.text() == str(tmp_path)
    assert view.first_frame.value() == 1 and view.last_frame.value() == 4
    assert view.format.currentText() == "parquet"
    assert not hasattr(view, "run_button")
    assert not hasattr(view, "status")
    assert not hasattr(view, "workers")
    output = tmp_path / "custom"
    monkeypatch.setattr(QFileDialog, "getExistingDirectory", lambda *args: str(output))
    view.browse.click()
    view.format.setCurrentText(fmt)
    view.first_frame.setValue(2)
    view.last_frame.setValue(3)
    window.right_panel.get_play_button(PipelineStep.BATCH).click()
    assert pipeline.model.get_status(PipelineStep.ROI) == StepStatus.RUNNING
    assert pipeline.model.get_status(PipelineStep.BATCH) == StepStatus.PENDING
    assert not output.exists()
    pipeline.model.set_batch_results(detections.iloc[:0] if empty else detections, metadata)
    complete_analysis(pipeline)
    assert not view.isEnabled()
    qtbot.waitUntil(lambda: view.isEnabled(), timeout=20000)
    assert pipeline.model.get_status(PipelineStep.BATCH) == StepStatus.COMPLETED
    assert pipeline.model.is_complete
    table = output / f"sample_blobs.{fmt}"
    details = window.right_panel.bottom_stats.details_label.text()
    if empty:
        assert not table.exists()
        assert "No detections found" in details
    else:
        loaded = read_table(table)
        assert loaded["frame"].tolist() == [1, 2]
        assert loaded["label"].tolist() == [8, 9]
        assert loaded["t_s"].tolist() == [0.5, 1.0]
        assert str(table) in details
    saved = json.loads((output / "sample_blobs_params.json").read_text())
    assert saved["blob"] == metadata["blob"]
    assert saved["info"] == metadata["info"]
    assert saved["channel"] == 1 and saved["t0"] == 1 and saved["t1"] == 2
    assert window.right_panel.bottom_stats.progress.isHidden()
    source.read.assert_not_called()


def test_missing_results_do_not_trigger_new_analysis(setup_batch):
    window, controller, files, source, pipeline, detections, metadata = setup_batch
    complete_analysis(pipeline)
    window.right_panel.get_play_button(PipelineStep.BATCH).click()
    assert pipeline.model.get_status(PipelineStep.BATCH) == StepStatus.IDLE
    assert "No processed pipeline data" in window.right_panel.bottom_stats.details_label.text()
    source.read.assert_not_called()


def test_write_error_is_reported_in_pipeline(setup_batch, qtbot, monkeypatch):
    window, controller, files, source, pipeline, detections, metadata = setup_batch
    pipeline.model.set_batch_results(detections, metadata)
    complete_analysis(pipeline)

    def fail(**kwargs):
        raise PermissionError("denied")

    monkeypatch.setattr("apkit4d.gui.controllers.batch_controller.save_batch_results", fail)
    window.right_panel.get_play_button(PipelineStep.BATCH).click()
    qtbot.waitUntil(lambda: window.right_panel.batch_inspector.isEnabled(), timeout=20000)
    assert pipeline.model.get_status(PipelineStep.BATCH) == StepStatus.IDLE
    assert "denied" in window.right_panel.bottom_stats.details_label.text()


@pytest.mark.parametrize("first,last,expected", [(1, 4, [0, 1, 2, 3]), (1, 1, [0]), (4, 4, [3])])
def test_one_based_selection_preserves_stored_frame_indices(
    setup_batch,
    qtbot,
    tmp_path,
    first,
    last,
    expected,
):
    window, controller, files, source, pipeline, detections, metadata = setup_batch
    view = window.right_panel.batch_inspector
    view.first_frame.setValue(first)
    view.last_frame.setValue(last)
    pipeline.model.set_batch_results(detections, metadata)
    complete_analysis(pipeline)
    pipeline.run_pipeline()
    qtbot.waitUntil(lambda: view.isEnabled(), timeout=20000)
    assert read_table(tmp_path / "sample_blobs.parquet")["frame"].tolist() == expected


def test_reset_clears_prepared_results(setup_batch):
    window, controller, files, source, pipeline, detections, metadata = setup_batch
    pipeline.model.set_batch_results(detections, metadata)
    pipeline.reset_pipeline()
    assert pipeline.model.batch_results is None
    assert not pipeline.model.is_complete


def test_new_output_folder_reexports_without_repeating_analysis(setup_batch, qtbot, tmp_path):
    window, controller, files, source, pipeline, detections, metadata = setup_batch
    pipeline.model.set_batch_results(detections, metadata)
    complete_analysis(pipeline)
    pipeline.run_pipeline()
    view = window.right_panel.batch_inspector
    qtbot.waitUntil(lambda: view.isEnabled(), timeout=20000)
    view.output_dir.setText(str(tmp_path / "second"))
    pipeline.run_pipeline()
    qtbot.waitUntil(lambda: view.isEnabled(), timeout=20000)
    assert (tmp_path / "second" / "sample_blobs.parquet").is_file()
    assert pipeline.model.is_complete
    source.read.assert_not_called()


def test_batch_reset_to_defaults_restores_source_folder_format_and_frames(setup_batch, tmp_path):
    window, _controller, _files, _source, _pipeline, _detections, _metadata = setup_batch
    view = window.right_panel.batch_inspector

    view.output_dir.setText(str(tmp_path / "custom"))
    view.format.setCurrentText("csv")
    view.first_frame.setValue(2)
    view.last_frame.setValue(3)

    view.reset_btn.click()

    assert view.output_dir.text() == str(tmp_path)
    assert view.format.currentText() == "parquet"
    assert view.first_frame.value() == 1
    assert view.last_frame.value() == 4
