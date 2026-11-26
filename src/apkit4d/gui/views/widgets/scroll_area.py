"""
Scroll container components.

A modern slim scrollbar with seamless integration with the application theme.
"""

from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QWidget,
)

from apkit4d.gui.constants import names

__all__ = ["ModernScrollArea"]


class ModernScrollArea(QScrollArea):
    """
    Scroll area with a sleek, minimalist scrollbar following the application theme.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setObjectName(names.MODERN_SCROLL_AREA)  # the stylesheet of the theme removes its background
