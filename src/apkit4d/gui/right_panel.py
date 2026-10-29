"""
Right column of the main window.
"""

from PySide6.QtWidgets import QPushButton

from apkit4d.gui.side_panel import SidePanel


class RightPanel(SidePanel):
    """Right column. Its controls will be added here."""

    def __init__(self) -> None:
        super().__init__("RIGHT (temp.)")
        self.add_control(QPushButton("RIGHT PANEL"))
