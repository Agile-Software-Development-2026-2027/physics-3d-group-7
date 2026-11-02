"""
Controller of the main window.

It is the only place where the view meets the rest of the application: it will call the processing
classes and then update the view. Those classes are not developed yet, so for now it only changes the
view and calls nothing. The navigation through the frames is delegated to the `PlaybackController`,
the look of the application to the `ThemeController`.
"""

from pathlib import Path

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QApplication

from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.controllers.theme_controller import ThemeController
from apkit4d.gui.views.main_window import MainWindow


class MainController(QObject):
    """
    Connects the signals of the main window to the application logic.

    Args:
        window: The view to control.
        app: The application, whose look is controlled by the theme.
        parent: Qt parent, so the controller lives as long as the window.
    """

    def __init__(self, window: MainWindow, app: QApplication, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._playback_controller = PlaybackController(window.playback_bar, self)
        self._theme_controller = ThemeController(app, self)

        window.file_opened.connect(self._on_file_opened)
        window.left_panel.theme_switch_requested.connect(self._theme_controller.toggle)
        # TODO: when the 3D view exists, connect it to the controllers:
        #   self._playback_controller.frame_changed.connect(view.show_frame)
        #   self._theme_controller.theme_changed.connect(view.set_theme)

    @property
    def playback_controller(self) -> PlaybackController:
        """Controller of the playback bar."""
        return self._playback_controller

    @property
    def theme_controller(self) -> ThemeController:
        """Controller of the theme."""
        return self._theme_controller

    def _on_file_opened(self, _path: Path) -> None:
        # TODO: call the loader with the path and, only when it succeeds:
        #   self._playback_controller.set_frame_count(frame_count)
        #   self._playback_controller.go_to_frame(0)
        #   and enable the bar
        self._window.playback_bar.setEnabled(True)
