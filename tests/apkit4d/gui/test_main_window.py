from pathlib import Path
from unittest.mock import MagicMock

import pandas as pd
import pytest
from PySide6.QtCore import QEvent, QMimeData, QPoint, QPointF, Qt, QUrl
from PySide6.QtGui import QAction, QDragEnterEvent, QDragLeaveEvent, QDropEvent
from PySide6.QtWidgets import QApplication, QFileDialog, QLabel, QWidget

from apkit4d.core.models import DetectionConfig, TrackingConfig
from apkit4d.gui import app as gui_app
from apkit4d.gui.app import run
from apkit4d.gui.constants import application, names, shortcuts, texts
from apkit4d.gui.controllers.main_controller import MainController
from apkit4d.gui.controllers.task_runner import wait_for_background_tasks
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.mock import MockConfig, MockFrameSource
from apkit4d.io.session import PrecomputedSession
from apkit4d.tracking.linker import TrackingResult


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


def test_drop_surface_opens_a_czi_file(window, qtbot, czi_file):
    surface = window.findChild(QLabel, names.CENTER_PLACEHOLDER)
    assert not surface.property("dragActive")
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(czi_file))])

    drag_event = QDragEnterEvent(
        QPoint(0, 0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(surface, drag_event)
    assert drag_event.isAccepted()
    assert surface.property("dragActive")

    QApplication.sendEvent(surface, QDragLeaveEvent())
    assert not surface.property("dragActive")

    QApplication.sendEvent(
        surface,
        QDragEnterEvent(
            QPoint(0, 0),
            Qt.DropAction.CopyAction,
            mime_data,
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier,
        ),
    )
    assert surface.property("dragActive")

    drop_event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    with qtbot.waitSignal(window.file_opened) as blocker:
        QApplication.sendEvent(surface, drop_event)
    assert blocker.args == [czi_file]
    assert not surface.property("dragActive")


def test_drop_surface_opens_json_results(window, qtbot, tmp_path):
    results_file = tmp_path / "sample_blobs_params.json"
    results_file.write_text("{}")
    surface = window.findChild(QLabel, names.CENTER_PLACEHOLDER)
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(results_file))])
    drag_event = QDragEnterEvent(
        QPoint(0, 0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(surface, drag_event)
    assert drag_event.isAccepted()
    drop_event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.CopyAction,
        mime_data,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )

    with qtbot.waitSignal(window.results_opened) as blocker:
        QApplication.sendEvent(surface, drop_event)

    assert blocker.args == [results_file]


def test_center_switches_between_drop_surface_and_view_when_file_loads(window):
    view = QWidget()
    window.set_view(view)
    window.show()

    surface = window.findChild(QLabel, names.CENTER_PLACEHOLDER)
    assert surface.isVisible()
    assert not view.isVisible()

    window.set_current_file(Path("sample.czi"))
    assert view.isVisible()
    assert not surface.isVisible()

    window.set_current_file(None)
    assert surface.isVisible()
    assert not view.isVisible()


def test_quit_action_closes_the_window(window):
    window.show()
    window.findChild(QAction, "quit_action").trigger()
    assert not window.isVisible()


def test_export_video_action_requests_export(window, qtbot):
    action = window.findChild(QAction, names.EXPORT_VIDEO_ACTION)
    assert action is not None
    assert action.shortcut().toString() == shortcuts.EXPORT_VIDEO
    assert not action.isEnabled()

    with qtbot.assertNotEmitted(window.video_export_requested):
        action.trigger()

    window.set_current_file(Path("sample.czi"))
    assert action.isEnabled()
    with qtbot.waitSignal(window.video_export_requested):
        action.trigger()


def test_export_video_action_opens_dialog(window, qapp, monkeypatch):
    from apkit4d.gui.controllers import main_controller

    dialog = MagicMock()
    dialog_class = MagicMock(return_value=dialog)
    monkeypatch.setattr(main_controller, "VideoExportDialog", dialog_class)
    controller = MainController(window, qapp, window, view=MagicMock())
    window.set_current_file(Path("sample.czi"))

    window.findChild(QAction, names.EXPORT_VIDEO_ACTION).trigger()

    dialog_class.assert_called_once_with(controller._video_export_controller, window)
    dialog.exec.assert_called_once_with()


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


@pytest.mark.parametrize(
    ("name", "opened_as_results"), [("sample.czi", False), ("sample_blobs_params.json", True)]
)
def test_run_opens_a_recording_or_saved_results(qapp, monkeypatch, tmp_path, name, opened_as_results):  # pyright: ignore[reportUnusedParameter]
    fake_window = MagicMock()
    monkeypatch.setattr(gui_app, "MainWindow", lambda: fake_window)
    monkeypatch.setattr(gui_app, "Viewport", MagicMock)
    monkeypatch.setattr(gui_app, "MainController", lambda *_args, **_kwargs: MagicMock())
    monkeypatch.setattr(QApplication, "exec", lambda *_: 0)
    path = tmp_path / name

    assert run(path) == 0
    if opened_as_results:
        fake_window.results_opened.emit.assert_called_once_with(path)
        fake_window.open_file.assert_not_called()
    else:
        fake_window.open_file.assert_called_once_with(path)
        fake_window.results_opened.emit.assert_not_called()


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
    assert window.findChild(QAction, names.EXPORT_VIDEO_ACTION).isEnabled()
    assert window.playback_bar.isEnabled()
    assert texts.MOCK_SOURCE_NAME in window.windowTitle()

    # All processing stages up to tracking are marked completed and frame 0 blobs render immediately
    for step in (
        PipelineStep.ROI,
        PipelineStep.PREPROCESSING,
        PipelineStep.DETECTION,
        PipelineStep.TRACKING,
    ):
        assert controller.pipeline_model.get_status(step) == StepStatus.COMPLETED
    assert isinstance(controller.tracking_result, TrackingResult)
    assert view.show_blobs.called
    frame0_poly = view.show_blobs.call_args.args[0]
    assert frame0_poly.n_points == int((source.tracks["frame"] == 0).sum())
    assert view.show_trajectories.called
    assert view.show_trajectories.call_args.args[0].n_points == 0

    # Stepping to another frame updates volume, precomputed blobs, and live trajectories
    controller.playback_controller.go_to_frame(2)
    qtbot.waitUntil(lambda: view.show_volume.call_count >= 2, timeout=5000)
    wait_for_background_tasks()
    assert frames_seen == [2]
    frame2_poly = view.show_blobs.call_args.args[0]
    assert frame2_poly.n_points == int((source.tracks["frame"] == 2).sum())
    frame2_tracks = view.show_trajectories.call_args.args[0]
    assert frame2_tracks.n_points > 0

    # Closing the mock source resets the session pipeline and trajectory state cleanly
    controller.file_controller.close()
    assert not window.findChild(QAction, names.EXPORT_VIDEO_ACTION).isEnabled()
    assert controller.pipeline_model.get_status(PipelineStep.ROI) == StepStatus.IDLE
    assert controller.tracking_result is None
    assert view.clear_trajectories.called


def test_main_controller_apply_precomputed_session_supports_generic_session(qtbot, qapp, window):
    view = MagicMock()
    controller = MainController(window, qapp, window, view=view)

    tracks = pd.DataFrame(
        {
            "frame": [0, 1, 2],
            "x_um": [1.0, 2.0, 3.0],
            "y_um": [1.0, 2.0, 3.0],
            "z_um": [1.0, 1.0, 1.0],
            "track_id": [7, 7, 7],
            "volume_um3": [150.0, 150.0, 150.0],
        }
    )
    session = PrecomputedSession(
        tracking=TrackingResult(tracks=tracks, metadata={"num_tracks_retained": 1}),
        blob_params=DetectionConfig(threshold=0.25),
        tracking_config=TrackingConfig(min_len=2),
    )

    controller.apply_precomputed_session(session, dt_s=0.1)
    assert controller.pipeline_model.get_status(PipelineStep.TRACKING) == StepStatus.COMPLETED
    assert controller.pipeline_model.get_step_params(PipelineStep.DETECTION)["threshold"] == 0.25
    assert controller.pipeline_model.get_step_params(PipelineStep.TRACKING)["min_len"] == 2
    assert view.show_blobs.call_args.args[0].n_points == 1

    controller.playback_controller.set_frame_count(3)
    controller.playback_controller.go_to_frame(2)
    assert view.show_trajectories.call_args.args[0].n_points == 3


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
