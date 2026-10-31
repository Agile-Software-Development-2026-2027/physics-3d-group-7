"""
Right column of the main window.
"""

from PySide6.QtWidgets import QPushButton

from apkit4d.gui import constants
from apkit4d.gui.side_panel import SidePanel


class RightPanel(SidePanel):
    """Right column. Its controls will be added here."""

    def __init__(self) -> None:
        super().__init__(constants.NAME_RIGHT_PANEL)
        self.add_control(QPushButton("RIGHT PANEL"))
