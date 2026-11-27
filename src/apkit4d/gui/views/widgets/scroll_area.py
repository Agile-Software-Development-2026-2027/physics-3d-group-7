"""
Scroll container components.

A modern slim scrollbar with seamless integration with the application theme.
"""

from typing import override

from PySide6.QtCore import QSize, Qt
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

    @override
    def minimumSizeHint(self) -> QSize:
        """
        Smallest size, as wide as the content when the content scrolls only vertically.

        Qt lets a scroll area become narrower than its content, which is then cropped on the right. A
        column that holds this scroll area cannot be made narrower than its controls, the vertical
        scroll bar included, so the application never crops them.
        """
        hint = super().minimumSizeHint()
        content = self.widget()
        if content is None or self.horizontalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff:
            return hint
        width = (
            content.minimumSizeHint().width()
            + self.verticalScrollBar().sizeHint().width()
            + 2 * self.frameWidth()
        )
        return QSize(max(hint.width(), width), hint.height())
