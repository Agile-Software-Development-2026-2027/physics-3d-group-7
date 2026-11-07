"""
QSS stylesheet generators and styler classes for GUI components.

Centralizes all QSS styling, widget style application, and execution status
color resolutions for the application.
"""

from typing import Self

from PySide6.QtWidgets import QFrame, QPushButton, QScrollArea, QWidget

from apkit4d.gui.constants import names
from apkit4d.gui.models.pipeline_model import StepStatus
from apkit4d.gui.theme.themes import (
    DARK_COLORS,
    DARK_STATUS_COLORS,
    LIGHT_STATUS_COLORS,
    THEME_COLORS,
    Theme,
    ThemeColors,
)

__all__ = [
    "AccordionStyler",
    "RightPanelStyler",
    "ScrollAreaStyler",
    "ThemeStyler",
    "get_accordion_content_area_stylesheet",
    "get_accordion_header_frame_stylesheet",
    "get_accordion_play_button_stylesheet",
    "get_accordion_toggle_button_stylesheet",
    "get_bottom_stats_stylesheet",
    "get_right_panel_top_bar_stylesheet",
    "get_scroll_area_stylesheet",
    "get_scrollbar_stylesheet",
    "get_status_colors",
]


def get_status_colors(status: StepStatus, colors: ThemeColors) -> tuple[str, str]:
    """
    Return (bg_color, text_color) for a pipeline step status under the active theme.

    Args:
        status: The execution status (IDLE, PENDING, RUNNING, COMPLETED).
        colors: Colors of the active theme.

    Returns:
        Tuple of (background_hex, text_hex).
    """
    is_dark = colors.window == DARK_COLORS.window
    palette = DARK_STATUS_COLORS if is_dark else LIGHT_STATUS_COLORS

    if status == StepStatus.PENDING:
        return (palette.pending_bg, palette.pending_text)
    if status == StepStatus.RUNNING:
        return (palette.running_bg, palette.running_text)
    if status == StepStatus.COMPLETED:
        return (palette.completed_bg, palette.completed_text)
    return (colors.button, colors.button_text)


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


def get_scroll_area_stylesheet(colors: ThemeColors) -> str:
    """
    Generate stylesheet for ModernScrollArea combining container and scrollbar rules.

    Args:
        colors: Colors of the active theme.
    """
    scrollbar_css = get_scrollbar_stylesheet(colors)
    return f"""
        QScrollArea#{names.MODERN_SCROLL_AREA} {{
            border: none;
            background-color: transparent;
        }}
        {scrollbar_css}
    """


def get_accordion_header_frame_stylesheet(
    colors: ThemeColors,
    status: StepStatus = StepStatus.IDLE,
    is_expanded: bool = False,
) -> str:
    """
    Generate stylesheet for the accordion header container frame.

    Args:
        colors: Colors of the active theme.
        status: The execution status of the section.
        is_expanded: Whether the section is currently expanded.
    """
    bg_col, _ = get_status_colors(status, colors)
    bottom_radius = 0 if is_expanded else 4

    return f"""
        QFrame#{names.ACCORDION_HEADER_FRAME} {{
            background-color: {bg_col};
            border: 1px solid {colors.alternate_base};
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            border-bottom-left-radius: {bottom_radius}px;
            border-bottom-right-radius: {bottom_radius}px;
        }}
    """


def get_accordion_toggle_button_stylesheet(
    colors: ThemeColors,
    status: StepStatus = StepStatus.IDLE,
    is_expanded: bool = False,
) -> str:
    """
    Generate stylesheet for the accordion header toggle button.

    Args:
        colors: Colors of the active theme.
        status: The execution status of the section.
        is_expanded: Whether the section is currently expanded.
    """
    bg_col, text_col = get_status_colors(status, colors)
    is_dark = colors.window == DARK_COLORS.window
    hover_bg = "rgba(255, 255, 255, 0.05)" if is_dark else "rgba(0, 0, 0, 0.04)"
    checked_bg = colors.window if status == StepStatus.IDLE else bg_col
    bottom_radius = 0 if is_expanded else 4

    return f"""
        QPushButton#{names.ACCORDION_TOGGLE_BUTTON} {{
            background-color: {bg_col};
            color: {text_col};
            border: none;
            border-top-left-radius: 4px;
            border-bottom-left-radius: {bottom_radius}px;
            border-top-right-radius: 0px;
            border-bottom-right-radius: 0px;
            padding: 9px 10px;
            text-align: left;
            font-weight: bold;
            font-size: 13px;
        }}
        QPushButton#{names.ACCORDION_TOGGLE_BUTTON}:hover {{
            background-color: {hover_bg};
        }}
        QPushButton#{names.ACCORDION_TOGGLE_BUTTON}:checked {{
            background-color: {checked_bg};
            border-bottom-left-radius: 0px;
        }}
        QPushButton#{names.ACCORDION_TOGGLE_BUTTON}:checked:hover {{
            background-color: {hover_bg};
        }}
    """


def get_accordion_play_button_stylesheet(
    colors: ThemeColors,
    status: StepStatus = StepStatus.IDLE,
) -> str:
    """
    Generate stylesheet for the play or action button on the right of an accordion header.

    Args:
        colors: Colors of the active theme.
        status: The execution status of the section.
    """
    _, text_col = get_status_colors(status, colors)
    is_dark = colors.window == DARK_COLORS.window
    hover_bg = "rgba(255, 255, 255, 0.15)" if is_dark else "rgba(0, 0, 0, 0.08)"
    hover_border = "rgba(255, 255, 255, 0.25)" if is_dark else "rgba(0, 0, 0, 0.15)"
    pressed_bg = "rgba(255, 255, 255, 0.25)" if is_dark else "rgba(0, 0, 0, 0.15)"

    return f"""
        QPushButton#{names.PLAY_STAGE_BUTTON} {{
            background-color: transparent;
            color: {text_col};
            border: 1px solid transparent;
            border-radius: 4px;
            font-size: 12px;
            font-weight: bold;
            padding: 0px;
        }}
        QPushButton#{names.PLAY_STAGE_BUTTON}:hover {{
            background-color: {hover_bg};
            border-color: {hover_border};
        }}
        QPushButton#{names.PLAY_STAGE_BUTTON}:pressed {{
            background-color: {pressed_bg};
        }}
    """


def get_accordion_content_area_stylesheet(colors: ThemeColors) -> str:
    """
    Generate stylesheet for the accordion body content area frame and inner labels.

    Args:
        colors: Colors of the active theme.
    """
    return f"""
        QFrame#{names.ACCORDION_CONTENT_AREA} {{
            background-color: {colors.base};
            border: 1px solid {colors.alternate_base};
            border-top: none;
            border-bottom-left-radius: 4px;
            border-bottom-right-radius: 4px;
        }}
        QFrame#{names.ACCORDION_CONTENT_AREA} QLabel {{
            background-color: transparent;
            color: {colors.text};
            border: none;
        }}
    """


def get_right_panel_top_bar_stylesheet(colors: ThemeColors) -> str:
    """
    Generate stylesheet for the right panel's top controls bar.

    Args:
        colors: Colors of the active theme.
    """
    return f"""
        QFrame#{names.RIGHT_PANEL_TOP_BAR} {{
            background-color: {colors.window};
            border-bottom: 1px solid {colors.alternate_base};
        }}
        QPushButton#{names.TOGGLE_ALL_BUTTON} {{
            background-color: {colors.button};
            color: {colors.button_text};
            border: 1px solid {colors.alternate_base};
            border-radius: 4px;
            padding: 6px 8px;
            font-size: 11px;
            font-weight: bold;
        }}
        QPushButton#{names.TOGGLE_ALL_BUTTON}:hover {{
            background-color: {colors.alternate_base};
        }}
    """


def get_bottom_stats_stylesheet(colors: ThemeColors) -> str:
    """
    Generate stylesheet for the collapsible bottom statistics and diagnostics section.

    Args:
        colors: Colors of the active theme.
    """
    return f"""
        QFrame#{names.BOTTOM_STATS_SECTION} {{
            background-color: {colors.window};
            border-top: 1px solid {colors.alternate_base};
        }}
        QFrame#{names.BOTTOM_STATS_HEADER} {{
            background-color: transparent;
            border: none;
        }}
        QLabel#{names.BOTTOM_STATS_SUMMARY_LABEL} {{
            color: {colors.window_text};
            font-weight: bold;
            font-size: 12px;
            background-color: transparent;
            border: none;
        }}
        QPushButton#{names.BOTTOM_STATS_TOGGLE_BUTTON} {{
            background-color: {colors.button};
            color: {colors.button_text};
            border: 1px solid {colors.alternate_base};
            border-radius: 3px;
            font-size: 10px;
            padding: 0px;
        }}
        QPushButton#{names.BOTTOM_STATS_TOGGLE_BUTTON}:hover {{
            background-color: {colors.alternate_base};
        }}
        QFrame#{names.BOTTOM_STATS_DETAILS_FRAME} {{
            background-color: {colors.base};
            border-top: 1px solid {colors.alternate_base};
        }}
        QLabel#{names.BOTTOM_STATS_DETAILS_LABEL} {{
            color: {colors.text};
            font-size: 11px;
            background-color: transparent;
            border: none;
        }}
    """


class AccordionStyler:
    """Styler helper for accordion sections."""

    @staticmethod
    def status_colors(status: StepStatus, colors: ThemeColors) -> tuple[str, str]:
        """Return (bg_color, text_color) for a status."""
        return get_status_colors(status, colors)

    @staticmethod
    def header_frame_stylesheet(
        colors: ThemeColors,
        status: StepStatus = StepStatus.IDLE,
        is_expanded: bool = False,
    ) -> str:
        """Return header frame QSS."""
        return get_accordion_header_frame_stylesheet(colors, status, is_expanded)

    @staticmethod
    def toggle_button_stylesheet(
        colors: ThemeColors,
        status: StepStatus = StepStatus.IDLE,
        is_expanded: bool = False,
    ) -> str:
        """Return toggle button QSS."""
        return get_accordion_toggle_button_stylesheet(colors, status, is_expanded)

    @staticmethod
    def play_button_stylesheet(
        colors: ThemeColors,
        status: StepStatus = StepStatus.IDLE,
    ) -> str:
        """Return accordion play button QSS."""
        return get_accordion_play_button_stylesheet(colors, status)

    @staticmethod
    def content_area_stylesheet(colors: ThemeColors) -> str:
        """Return content area QSS."""
        return get_accordion_content_area_stylesheet(colors)

    @staticmethod
    def apply(
        toggle_button: QPushButton,
        content_area: QFrame,
        colors: ThemeColors,
        status: StepStatus = StepStatus.IDLE,
        play_button: QPushButton | None = None,
        header_frame: QFrame | None = None,
        is_expanded: bool = False,
    ) -> None:
        """Apply theme styling directly to accordion components."""
        if header_frame is not None:
            header_frame.setStyleSheet(get_accordion_header_frame_stylesheet(colors, status, is_expanded))
        toggle_button.setStyleSheet(get_accordion_toggle_button_stylesheet(colors, status, is_expanded))
        content_area.setStyleSheet(get_accordion_content_area_stylesheet(colors))
        if play_button is not None:
            play_button.setStyleSheet(get_accordion_play_button_stylesheet(colors, status))


class ScrollAreaStyler:
    """Styler helper for modern scroll area and scrollbars."""

    @staticmethod
    def scrollbar_stylesheet(colors: ThemeColors) -> str:
        """Return scrollbar QSS."""
        return get_scrollbar_stylesheet(colors)

    @staticmethod
    def scroll_area_stylesheet(colors: ThemeColors) -> str:
        """Return scroll area QSS."""
        return get_scroll_area_stylesheet(colors)

    @staticmethod
    def apply(scroll_area: QScrollArea, colors: ThemeColors) -> None:
        """Apply theme styling directly to a scroll area."""
        scroll_area.setStyleSheet(get_scroll_area_stylesheet(colors))


class RightPanelStyler:
    """Styler helper for the right panel components."""

    @staticmethod
    def top_bar_stylesheet(colors: ThemeColors) -> str:
        """Return top bar QSS."""
        return get_right_panel_top_bar_stylesheet(colors)

    @staticmethod
    def bottom_stats_stylesheet(colors: ThemeColors) -> str:
        """Return bottom stats section QSS."""
        return get_bottom_stats_stylesheet(colors)

    @staticmethod
    def apply_bottom_stats(widget: QWidget, colors: ThemeColors) -> None:
        """Apply theme styling to the bottom stats widget."""
        widget.setStyleSheet(get_bottom_stats_stylesheet(colors))


class ThemeStyler:
    """
    Centralized object-oriented theme styler providing stylesheets for all components.

    Args:
        colors: Active ThemeColors instance.
    """

    def __init__(self, colors: ThemeColors) -> None:
        self._colors = colors

    @classmethod
    def for_theme(cls, theme: Theme) -> Self:
        """Instantiate a ThemeStyler for `theme`."""
        return cls(THEME_COLORS[theme])

    @property
    def colors(self) -> ThemeColors:
        """Underlying theme colors."""
        return self._colors

    def status_colors(self, status: StepStatus) -> tuple[str, str]:
        """Return (bg_color, text_color) for `status`."""
        return get_status_colors(status, self._colors)

    def scrollbar(self) -> str:
        """Return scrollbar QSS."""
        return get_scrollbar_stylesheet(self._colors)

    def scroll_area(self) -> str:
        """Return scroll area QSS."""
        return get_scroll_area_stylesheet(self._colors)

    def accordion_header_frame(self, status: StepStatus = StepStatus.IDLE, is_expanded: bool = False) -> str:
        """Return accordion header frame QSS for `status`."""
        return get_accordion_header_frame_stylesheet(self._colors, status, is_expanded)

    def accordion_toggle_button(self, status: StepStatus = StepStatus.IDLE, is_expanded: bool = False) -> str:
        """Return accordion toggle button QSS for `status`."""
        return get_accordion_toggle_button_stylesheet(self._colors, status, is_expanded)

    def accordion_play_button(self, status: StepStatus = StepStatus.IDLE) -> str:
        """Return accordion play button QSS for `status`."""
        return get_accordion_play_button_stylesheet(self._colors, status)

    def accordion_content_area(self) -> str:
        """Return accordion content area QSS."""
        return get_accordion_content_area_stylesheet(self._colors)

    def right_panel_top_bar(self) -> str:
        """Return right panel top bar QSS."""
        return get_right_panel_top_bar_stylesheet(self._colors)

    def bottom_stats(self) -> str:
        """Return bottom stats QSS."""
        return get_bottom_stats_stylesheet(self._colors)
