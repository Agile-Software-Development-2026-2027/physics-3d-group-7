from unittest.mock import MagicMock

import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog

from apkit4d.gui import app as gui_app
from apkit4d.gui.app import run
from apkit4d.gui.constants import application, texts
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.task_runner import wait_for_background_tasks
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.mock import MockConfig, MockFrameSource


@pytest.fixture
def window(qtbot):
    win = MainWindow()
    qtbot.addWidget(win)
    return win


@pytest.fixture
def czi_file(tmp_path):
    path = tmp_path / "sample.czi"
    path.write_bytes(b"")
    return path


def test_open_file_emits_the_path(window, qtbot, czi_file):
    with qtbot.waitSignal(window.file_opened):
        assert window.open_file(czi_file)


def test_open_file_rejects_other_formats(window, qtbot, tmp_path):
    path = tmp_path / "sample.tif"
    path.write_bytes(b"")
    with qtbot.assertNotEmitted(window.file_opened):
        assert not window.open_file(path)


def test_open_file_rejects_missing_files(window, qtbot, tmp_path):
    with qtbot.assertNotEmitted(window.file_opened):
        assert not window.open_file(tmp_path / "missing.czi")


def test_open_action_opens_the_chosen_file(window, qtbot, czi_file, monkeypatch):
    # the user picks czi_file in the file dialog
    monkeypatch.setattr(QFileDialog, "getOpenFileName", lambda *args: (str(czi_file), ""))
    with qtbot.waitSignal(window.file_opened) as blocker:
        window.findChild(QAction, "open_action").trigger()
    assert blocker.args == [czi_file]


def test_quit_action_closes_the_window(window):
    window.show()
    window.findChild(QAction, "quit_action").trigger()
    assert not window.isVisible()


def test_run_returns_the_exit_code_of_the_application(qapp, czi_file, monkeypatch):
    monkeypatch.setattr(QApplication, "exec", lambda *_: 0)
    assert run(czi_file) == 0


def test_open_file_leaves_the_title_and_the_status_to_whoever_reads_the_file(window, czi_file):
    window.open_file(czi_file)
    assert window.windowTitle() == application.APP_NAME
    assert window.statusBar().currentMessage() == texts.STATUS_NO_FILE


def test_run_with_mock_opens_mock_source(qapp, monkeypatch):  # pyright: ignore[reportUnusedParameter]
    fake_controller = MagicMock()
    fake_window = MagicMock()
    monkeypatch.setattr(gui_app, "MainWindow", lambda: fake_window)
    monkeypatch.setattr(gui_app, "Viewport", MagicMock)
    monkeypatch.setattr(gui_app, "MainController", lambda *_args, **_kwargs: fake_controller)
    monkeypatch.setattr(QApplication, "exec", lambda *_: 0)

    assert run(mock=True) == 0
    fake_window.show.assert_called_once()
    fake_controller.open_mock.assert_called_once()
    fake_window.open_file.assert_not_called()


def test_main_controller_open_mock_loads_source_and_playback(qtbot, qapp, window):
    view = MagicMock()
    controller = MainController(window, qapp, window, view=view)
    frames_seen: list[int] = []
    controller.playback_controller.frame_changed.connect(frames_seen.append)

    controller.open_mock(MockConfig(n_t=6, n_z=8, n_y=24, n_x=24))
    qtbot.waitUntil(lambda: isinstance(controller.file_controller.source, MockFrameSource), timeout=5000)
    qtbot.waitUntil(lambda: view.show_volume.called, timeout=5000)
    wait_for_background_tasks()

    source = controller.file_controller.source
    assert isinstance(source, MockFrameSource)
    assert controller.playback_controller.frame_count == 6
    assert window.playback_bar.isEnabled()
    assert texts.MOCK_SOURCE_NAME in window.windowTitle()

    # Stepping to another frame updates the mock volume view live
    controller.playback_controller.go_to_frame(2)
    qtbot.waitUntil(lambda: view.show_volume.call_count >= 2, timeout=5000)
    wait_for_background_tasks()
    assert frames_seen == [2]
