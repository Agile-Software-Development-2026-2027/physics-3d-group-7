from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QFileDialog

from apkit4d.core.roi import RegionOfInterest
from apkit4d.gui.controllers import multi_file_controller
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.models.pipeline_model import PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.mock import MockConfig, MockFrameSource
from apkit4d.io.saved_results import read_saved_results
from apkit4d.io.session import PrecomputedFrameSource


class FakeCzi(MockFrameSource):
    def __init__(self, path: Path, channel: int = 0) -> None:
        depth = 7 if path.name == "small.czi" else 8
        super().__init__(MockConfig(n_t=2, n_z=depth, n_y=24, n_x=24))
        self.path = path
        self.channel = channel

    @property
    def info(self):
        info = super().info
        if self.path.name == "different.czi":
            return replace(info, path=str(self.path), n_t=1)
        return replace(info, path=str(self.path))


def test_multi_file_menu_runs_independent_pipeline_exports(qapp, qtbot, tmp_path, monkeypatch):
    first = tmp_path / "source.czi"
    second = tmp_path / "copy" / first.name
    different = tmp_path / "different.czi"
    second.parent.mkdir()
    for path in (first, second, different):
        path.touch()

    monkeypatch.setattr(multi_file_controller, "CziSource", FakeCzi)
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window, open_source=FakeCzi)
    files = controller.file_controller
    panel = window.multi_file_panel
    assert not window.add_files_action.isEnabled()
    assert not panel.run.isEnabled()

    selected = [str(first), str(different)]
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: (selected, ""))
    with qtbot.waitSignal(files.loaded):
        window.open_files_action.trigger()
    assert files.source.path == first
    assert panel.recordings.count() == 2

    selected = [str(first), str(second)]
    window.add_files_action.trigger()
    assert files.source.path == first
    assert panel.recordings.count() == 3
    root = QModelIndex()
    assert panel.recordings.model().moveRow(root, 2, root, 0)
    assert files.source.path == first

    output = tmp_path / "exports"
    output.mkdir()
    export = window.right_panel.batch_inspector
    export.output_dir.setText(str(output))
    export.format.setCurrentText("csv")
    export.first_frame.setValue(2)
    panel.run.click()
    assert not panel.run.isEnabled()
    qtbot.waitUntil(panel.run.isEnabled, timeout=15000)
    assert panel.status.text() == "Saved results for 2 of 3 recordings."
    assert "Export ends at frame 2" in panel.recordings.item(2).text()

    results = [read_saved_results(path) for path in output.glob("apkit4d-batch-*/*/*_params.json")]
    assert len(results) == 2
    saved_recordings = [result.recording for result in results]
    assert first in saved_recordings
    assert second in saved_recordings
    for result in results:
        assert result.params_path.parent.name == ("1" if result.recording == second else "2")
        assert result.metadata["format"] == "csv"
        assert (result.metadata["t0"], result.metadata["t1"]) == (1, 1)
        session = result.load_session()
        assert session.blobs is not None
        assert session.tracking is not None

    with qtbot.assertNotEmitted(files.loaded):
        panel.recordings.itemDoubleClicked.emit(panel.recordings.item(2))
    panel.recordings.setCurrentRow(2)
    panel.remove.click()
    assert panel.recordings.count() == 2
    assert different.is_file()

    for row, expected_recording in ((0, second), (1, first)):
        item = panel.recordings.item(row)
        with qtbot.waitSignal(files.loaded):
            panel.recordings.itemDoubleClicked.emit(item)
        source = files.source
        assert isinstance(source, PrecomputedFrameSource)
        assert source.path == expected_recording
        assert source.session.metadata["t0"] == 1
        assert source.session.tracking is not None
        assert item.font().bold()

    assert not panel.recordings.item(0).font().bold()
    controller.pipeline_model.update_step_params(PipelineStep.DETECTION, threshold=0.25)
    export.output_dir.setText(str(output))
    export.format.setCurrentText("csv")
    export.first_frame.setValue(2)
    panel.recordings.setCurrentRow(1)
    with qtbot.waitSignal(files.loaded):
        panel.remove.click()
    assert files.source.path == second
    assert not isinstance(files.source, PrecomputedFrameSource)
    assert controller.pipeline_model.get_step_params(PipelineStep.DETECTION)["threshold"] == 0.25
    assert export.output_dir.text() == str(output)
    assert export.format.currentText() == "csv"
    assert export.first_frame.value() == 2
    assert all(result.params_path.is_file() for result in results)
    assert first.is_file()
    assert panel.recordings.count() == 1
    panel.recordings.setCurrentRow(0)
    assert not panel.remove.isEnabled()
    panel.remove.click()
    assert panel.recordings.count() == 1
    assert files.source.path == second
    assert not panel.recordings.item(0).font().bold()


def test_add_files_starts_a_queue_with_the_active_recording(qapp, qtbot, tmp_path, monkeypatch):
    first = tmp_path / "first.czi"
    second = tmp_path / "second.czi"
    first.touch()
    second.touch()
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window, open_source=FakeCzi)

    with qtbot.waitSignal(controller.file_controller.loaded):
        assert window.open_file(first)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(second)], ""))
    window.add_files_action.trigger()

    panel = window.multi_file_panel
    assert panel.recordings.count() == 2
    assert panel.recordings.item(0).text().startswith(first.name)
    assert panel.recordings.item(1).text().startswith(second.name)
    assert controller.file_controller.source.path == first

    controller.pipeline_model.update_step_params(PipelineStep.DETECTION, threshold=0.25)
    export = window.right_panel.batch_inspector
    export.format.setCurrentText("csv")
    for row, path in ((1, second), (0, first)):
        with qtbot.waitSignal(controller.file_controller.loaded):
            panel.recordings.itemDoubleClicked.emit(panel.recordings.item(row))
        assert controller.file_controller.source.path == path
        assert controller.pipeline_model.get_step_params(PipelineStep.DETECTION)["threshold"] == 0.25
        assert export.format.currentText() == "csv"
        assert panel.recordings.count() == 2


def test_batch_can_mix_common_and_personalized_recording_settings(qapp, qtbot, tmp_path, monkeypatch):
    first = tmp_path / "first.czi"
    second = tmp_path / "small.czi"
    first.touch()
    second.touch()
    frames_read = []

    class RecordingSpy(FakeCzi):
        def read(self, t):
            frames_read.append((self.path, t))
            return super().read(t)

    monkeypatch.setattr(multi_file_controller, "CziSource", RecordingSpy)
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", lambda *args: ([str(first), str(second)], ""))
    window = MainWindow()
    qtbot.addWidget(window)
    controller = MainController(window, qapp, window, open_source=FakeCzi)
    files = controller.file_controller
    panel = window.multi_file_panel
    model = controller.pipeline_model
    export = window.right_panel.batch_inspector

    with qtbot.waitSignal(files.loaded):
        window.open_files_action.trigger()
    qtbot.keyClick(panel.settings_mode, Qt.Key.Key_Down)

    roi = RegionOfInterest(0, 2, 0, 2, 0, 2)
    model.set_roi_params(model.get_roi_params().with_region(roi))
    model.update_step_params(PipelineStep.DETECTION, threshold=0.25)
    export.last_frame.setValue(1)

    with qtbot.waitSignal(files.loaded):
        panel.recordings.itemDoubleClicked.emit(panel.recordings.item(1))
    assert panel.settings_mode.currentIndex() == 0
    assert model.get_roi_params().region is None
    model.update_step_params(PipelineStep.DETECTION, threshold=0.35)
    export.first_frame.setValue(2)

    with qtbot.waitSignal(files.loaded):
        panel.recordings.itemDoubleClicked.emit(panel.recordings.item(0))
    assert panel.settings_mode.currentIndex() == 1
    assert model.get_roi_params().region == roi
    assert export.last_frame.value() == 1

    panel.run.click()
    qtbot.waitUntil(panel.run.isEnabled, timeout=15000)
    assert panel.status.text() == "Saved results for 2 of 2 recordings."
    assert frames_read == [(first, 0), (second, 1)]
    results = {}
    for path in tmp_path.glob("apkit4d-batch-*/*/*_params.json"):
        result = read_saved_results(path)
        results[result.recording] = result
    assert results[first].metadata["blob"]["threshold"] == 0.25
    assert results[second].metadata["blob"]["threshold"] == 0.35
    assert results[first].load_session().roi == roi
    assert results[second].load_session().roi is None
    assert (results[first].metadata["t0"], results[first].metadata["t1"]) == (0, 0)
    assert (results[second].metadata["t0"], results[second].metadata["t1"]) == (1, 1)

    qtbot.keyClick(panel.settings_mode, Qt.Key.Key_Up)
    assert model.get_roi_params().region is None
    assert model.get_step_params(PipelineStep.DETECTION)["threshold"] == 0.35
    assert export.first_frame.value() == 2
    assert export.last_frame.value() == 2

    qtbot.keyClick(panel.settings_mode, Qt.Key.Key_Down)
    assert model.get_roi_params().region == roi
    assert export.last_frame.value() == 1
    qtbot.keyClick(panel.settings_mode, Qt.Key.Key_Up)

    panel.run.click()
    qtbot.waitUntil(panel.run.isEnabled, timeout=15000)
    assert panel.status.text() == "Saved results for 2 of 2 recordings."

    # A shared crop can fit one recording and exceed the other recording's bounds.
    common_roi = RegionOfInterest(0, 20, 0, 20, 0, 110)
    model.set_roi_params(model.get_roi_params().with_region(common_roi))
    panel.run.click()
    qtbot.waitUntil(panel.run.isEnabled, timeout=15000)
    assert panel.status.text() == "Saved results for 1 of 2 recordings."
    assert "ROI extends outside this recording" in panel.recordings.item(1).text()
