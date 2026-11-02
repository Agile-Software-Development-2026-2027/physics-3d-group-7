"""
Controller of the theme: keeps the active theme and changes it.

The 3D view and any other component that draws by itself (graphs, for example) connect to
`theme_changed` to follow the theme, because the palette does not reach them.
"""

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from apkit4d.gui.theme import DEFAULT_THEME, Theme, apply_theme


class ThemeController(QObject):
    """
    Keeps the active theme, applies it to the application and announces its changes.

    The default theme is applied as soon as the controller is created.

    Args:
        app: The application to paint.
        parent: Qt parent, so the controller lives as long as its owner.

    Signals:
        theme_changed: Emitted with the new `Theme` every time the active theme changes.
    """

    theme_changed = Signal(object)  # object, because the payload is a Python enum

    def __init__(self, app: QApplication, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._app = app
        self._theme = DEFAULT_THEME
        apply_theme(app, self._theme)

    @property
    def theme(self) -> Theme:
        """The active theme."""
        return self._theme

    def set_theme(self, theme: Theme) -> None:
        """
        Apply `theme`. Nothing happens if it is already the active one.

        Args:
            theme: Theme to apply.
        """
        if theme is self._theme:
            return
        self._theme = theme
        apply_theme(self._app, theme)
        self.theme_changed.emit(theme)

    def toggle(self) -> None:
        """Switch to the other theme."""
        self.set_theme(self._theme.opposite)
