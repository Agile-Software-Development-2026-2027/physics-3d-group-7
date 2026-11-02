"""
Right column of the main window.
"""

from PySide6.QtWidgets import QPushButton

from apkit4d.gui.constants import names, texts
from apkit4d.gui.views.panels.side_panel import SidePanel


class RightPanel(SidePanel):
    """Right column. Its controls will be added here."""

    def __init__(self) -> None:
        super().__init__(names.RIGHT_PANEL)
        self.add_control(QPushButton(texts.RIGHT_PANEL_PLACEHOLDER))  # TODO: replace with the real controls
