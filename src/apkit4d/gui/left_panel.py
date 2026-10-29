"""
Left column of the main window.
"""

from PySide6.QtWidgets import QPushButton

from apkit4d.gui import constants
from apkit4d.gui.side_panel import SidePanel


class LeftPanel(SidePanel):
    """Left column. Its controls will be added here."""

    def __init__(self) -> None:
        super().__init__(constants.NAME_LEFT_PANEL)
        self.add_control(QPushButton("LEFT PANEL"))
