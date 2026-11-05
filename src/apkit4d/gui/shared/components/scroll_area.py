"""
And scroll container components.

A modern slim scrollbar with seamless (kinda) integration with the application theme.
"""

from PySide6.QtWidgets import (
    QFrame,
    QScrollArea,
    QWidget,
)

from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, ThemeColors


def get_scrollbar_stylesheet(colors: ThemeColors) -> str:
    """
    Generate a modern, slim scrollbar stylesheet matching the given theme colors.

    Args:
        colors: Colors of the active theme.

    Returns:
        QSS string for vertical and horizontal scrollbars.
    """
    thumb_color = colors.placeholder_text
    hover_color = colors.highlight
    pressed_color = colors.link

    return f"""
        QScrollBar:vertical {{
            border: none;
            background: transparent;
            width: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:vertical {{
            background: {thumb_color};
            min-height: 24px;
            border-radius: 4px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {hover_color};
        }}
        QScrollBar::handle:vertical:pressed {{
            background: {pressed_color};
        }}
        QScrollBar::sub-line:vertical, QScrollBar::add-line:vertical {{
            border: none;
            background: none;
            height: 0px;
        }}
        QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {{
            background: none;
        }}
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
            background: none;
        }}

        QScrollBar:horizontal {{
            border: none;
            background: transparent;
            height: 8px;
            margin: 0px;
        }}
        QScrollBar::handle:horizontal {{
            background: {thumb_color};
            min-width: 24px;
            border-radius: 4px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {hover_color};
        }}
        QScrollBar::handle:horizontal:pressed {{
            background: {pressed_color};
        }}
        QScrollBar::sub-line:horizontal, QScrollBar::add-line:horizontal {{
            border: none;
            background: none;
            width: 0px;
        }}
        QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {{
            background: none;
        }}
        QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
            background: none;
        }}
    """


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
        self.setObjectName("modernScrollArea")
        self.apply_theme(THEME_COLORS[DEFAULT_THEME])

    def apply_theme(self, colors: ThemeColors) -> None:
        """
        Update scrollbar styles to match the given theme colors.

        Args:
            colors: Colors of the active theme.
        """
        scrollbar_css = get_scrollbar_stylesheet(colors)
        self.setStyleSheet(f"""
            QScrollArea#modernScrollArea {{
                border: none;
                background-color: transparent;
            }}
            {scrollbar_css}
        """)
