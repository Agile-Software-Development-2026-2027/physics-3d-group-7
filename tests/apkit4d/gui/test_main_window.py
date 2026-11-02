import pytest
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QFileDialog

from apkit4d.gui.app import run
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
    with qtbot.waitSignal(window.file_opened) as blocker:
        assert window.open_file(czi_file)
    assert blocker.args == [czi_file]
    assert window.statusBar().currentMessage() == str(czi_file)


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


def test_run_shows_the_window_and_returns_when_closed(qapp, czi_file):
    QTimer.singleShot(0, qapp.quit)
    assert run(czi_file) == 0
