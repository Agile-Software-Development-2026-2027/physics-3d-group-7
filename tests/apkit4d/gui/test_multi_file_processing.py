from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QFileDialog

from apkit4d.gui.controllers import multi_file_controller
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.models.pipeline_model import PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.mock import MockConfig, MockFrameSource
from apkit4d.io.saved_results import read_saved_results
from apkit4d.io.session import PrecomputedFrameSource


class FakeCzi(MockFrameSource):
    def __init__(self, path: Path, channel: int = 0) -> None:
        super().__init__(MockConfig(n_t=2, n_z=8, n_y=24, n_x=24))
        self.path = path
        self.channel = channel

    @property
    def info(self):
        info = super().info
        if self.path.name == "different.czi":
            return replace(info, path=str(self.path), n_z=7)
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
    assert "Volume dimensions differ" in panel.recordings.item(2).text()

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
