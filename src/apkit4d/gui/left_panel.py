"""
Left column of the main window.
"""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QPushButton

from apkit4d.gui import constants
from apkit4d.gui.side_panel import SidePanel


class LeftPanel(SidePanel):
    """
    Left column. It holds the button that switches the theme, for now.

    Signals:
        theme_switch_requested: The user pressed the theme button.
    """

    theme_switch_requested = Signal()

    def __init__(self) -> None:
        super().__init__(constants.NAME_LEFT_PANEL)
        theme_button = QPushButton(constants.TEXT_BUTTON_THEME)
        theme_button.setObjectName(constants.NAME_THEME_BUTTON)
        theme_button.clicked.connect(self.theme_switch_requested)
        self.add_control(theme_button)
