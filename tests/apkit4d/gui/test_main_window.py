import pytest
from PySide6.QtCore import QEvent
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QWidget

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


def test_show_fps_action_toggles_label_and_timer(window):
    action = window.findChild(QAction, "show_fps_action")
    label = window.findChild(QLabel, "fps_label")

    assert action is not None
    assert action.isCheckable()
    assert not action.isChecked()
    assert label is not None
    assert not label.isVisible()
    assert not window._fps_timer.isActive()

    action.trigger()
    assert action.isChecked()
    assert not label.isHidden()
    assert window._fps_timer.isActive()

    action.trigger()
    assert not action.isChecked()
    assert label.isHidden()
    assert not window._fps_timer.isActive()


def test_fps_label_displays_qt_and_vtk_rates(window, monkeypatch):
    class FakeRenderView(QWidget):
        @property
        def render_fps(self) -> float:
            return 42.5

    view = FakeRenderView()
    window.set_view(view)
    window.show()

    now = 50.0
    monkeypatch.setattr("time.perf_counter", lambda: now)

    action = window.findChild(QAction, "show_fps_action")
    label = window.findChild(QLabel, "fps_label")
    action.setChecked(True)

    # Simulate two Qt paint cycles 100 ms apart -> 10.0 FPS
    window.eventFilter(window, QEvent(QEvent.Type.Paint))
    QApplication.processEvents()
    now += 0.1
    window.eventFilter(window, QEvent(QEvent.Type.Paint))
    QApplication.processEvents()

    window._update_fps_label()
    assert label.text() == texts.FPS_READOUT.format(qt_fps=10.0, render_fps=42.5)
    assert label.minimumWidth() == label.maximumWidth()
    assert label.width() > 0


def test_fps_event_filter_coalesces_multiple_child_paints_per_frame(window, monkeypatch):
    child_a = QWidget(window)
    child_b = QWidget(window)

    now = 200.0
    monkeypatch.setattr("time.perf_counter", lambda: now)

    action = window.findChild(QAction, "show_fps_action")
    action.setChecked(True)

    # Frame 1: multiple widgets paint in the same event-loop turn before singleShot(0) fires
    window.eventFilter(child_a, QEvent(QEvent.Type.Paint))
    window.eventFilter(child_b, QEvent(QEvent.Type.Paint))
    QApplication.processEvents()

    # Frame 2: 50 ms later, multiple widgets paint again -> 20.0 FPS (not 40+ FPS)
    now += 0.05
    window.eventFilter(child_a, QEvent(QEvent.Type.Paint))
    window.eventFilter(child_b, QEvent(QEvent.Type.Paint))
    QApplication.processEvents()

    assert window._qt_fps_ticker.fps() == pytest.approx(20.0)
