"""
Controller of the main window.

It is the only place where the view meets the rest of the application. It creates the other controllers
and connects them: the `FileController` opens the files, the `PlaybackController` moves through the
frames, the `VolumeController` shows them in the 3D view, the `ThemeController` changes the look of the
application.
"""

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from apkit4d.gui.controllers.file_controller import FileController, FrameSource, SourceOpener
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.theme_controller import ThemeController
from apkit4d.gui.controllers.volume_controller import VolumeController, VolumeView
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziSource


class MainController(QObject):
    """
    Connects the signals of the main window to the application logic.

    Args:
        window: The view to control.
        app: The application, whose look is controlled by the theme.
        parent: Qt parent, so the controller lives as long as the window.
        open_source: Function that opens a file and returns its recording, `CziSource` unless a test
            needs a fake one.
        view: The 3D view that shows the frames. Without it the recording is opened but not shown.
    """

    def __init__(
        self,
        window: MainWindow,
        app: QApplication,
        parent: QObject | None = None,
        *,
        open_source: SourceOpener = CziSource,
        view: VolumeView | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._file_controller = FileController(window, open_source, self)
        self._playback_controller = PlaybackController(window.playback_bar, self)
        self._theme_controller = ThemeController(app, self)

        self._volume_controller = VolumeController(window, view, self) if view is not None else None
        if self._volume_controller is not None:
            # the volume controller must know the new recording before the playback goes back to frame 0
            self._file_controller.loaded.connect(self._volume_controller.set_source)
            self._playback_controller.frame_changed.connect(self._volume_controller.show_frame)
            self._volume_controller.failed.connect(self._on_volume_failed)
        self._file_controller.loaded.connect(self._on_file_loaded)

        window.left_panel.theme_switch_requested.connect(self._theme_controller.toggle)
        # TODO: the 3D view does not follow the theme yet: it needs a method to change its background,
        # and then `self._theme_controller.theme_changed.connect(view.set_theme)`

    @property
    def file_controller(self) -> FileController:
        """Controller of the opening of files."""
        return self._file_controller

    @property
    def playback_controller(self) -> PlaybackController:
        """Controller of the playback bar."""
        return self._playback_controller

    @property
    def theme_controller(self) -> ThemeController:
        """Controller of the theme."""
        return self._theme_controller

    @property
    def volume_controller(self) -> VolumeController | None:
        """Controller of the 3D view, None if the application has no 3D view."""
        return self._volume_controller

    def _on_file_loaded(self, _path: Path, source: FrameSource) -> None:
        playback = self._playback_controller
        playback.set_playing(False)
        playback.set_frame_count(source.info.n_t)
        playback.go_to_frame(0)
        self._window.playback_bar.setEnabled(True)

    def _on_volume_failed(self) -> None:
        self._playback_controller.set_playing(False)  # otherwise every frame would report the same error
