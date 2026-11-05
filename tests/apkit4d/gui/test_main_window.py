import pytest
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog

from apkit4d.gui.app import run
from apkit4d.gui.constants import application, texts
from apkit4d.gui.views.main_window import MainWindow


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
