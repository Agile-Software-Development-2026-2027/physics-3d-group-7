"""
Controller of the main window.

It is the only place where the view meets the rest of the application: it will call the
processing classes and then update the view. Those classes are not developed yet, so for
now it only changes the view and calls nothing. The navigation through the frames is
delegated to the `PlaybackController`.
"""

from pathlib import Path

from PySide6.QtCore import QObject

from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.main_window import MainWindow


class MainController(QObject):
    """
    Connects the signals of the main window to the application logic.

    Args:
        window: The view to control.
        parent: Qt parent, so the controller lives as long as the window.
    """

    def __init__(self, window: MainWindow, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._playback = PlaybackController(window.playback_bar, self)
        window.file_opened.connect(self._on_file_opened)
        # TODO: when the 3D view exists, show the right frame with:
        #   self._playback.frame_changed.connect(view.show_frame)

    @property
    def playback(self) -> PlaybackController:
        """Controller of the playback bar."""
        return self._playback

    def _on_file_opened(self, _path: Path) -> None:
        # TODO: call the loader with the path and, only when it succeeds:
        #   self._playback.set_frame_count(frame_count)
        #   self._playback.go_to_frame(0)
        #   and enable the bar
        self._window.playback_bar.setEnabled(True)
