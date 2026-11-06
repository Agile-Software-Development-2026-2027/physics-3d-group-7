"""
Unit tests for theme palettes, status colors, and QSS component stylers.
"""

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QFrame, QPushButton, QScrollArea, QWidget

from apkit4d.gui.constants import names
from apkit4d.gui.models.pipeline_model import StepStatus
from apkit4d.gui.theme import (
    DARK_COLORS,
    DARK_STATUS_COLORS,
    DEFAULT_THEME,
    LIGHT_COLORS,
    LIGHT_STATUS_COLORS,
    STATUS_THEME_COLORS,
    THEME_COLORS,
    AccordionStyler,
    RightPanelStyler,
    ScrollAreaStyler,
    Theme,
    ThemeStyler,
    apply_theme,
    build_palette,
    get_accordion_content_area_stylesheet,
    get_accordion_header_frame_stylesheet,
    get_accordion_play_button_stylesheet,
    get_accordion_toggle_button_stylesheet,
    get_bottom_stats_stylesheet,
    get_right_panel_top_bar_stylesheet,
    get_scroll_area_stylesheet,
    get_scrollbar_stylesheet,
    get_status_colors,
)


def test_theme_enum_and_defaults() -> None:
    assert Theme.LIGHT.opposite == Theme.DARK
    assert Theme.DARK.opposite == Theme.LIGHT
    assert DEFAULT_THEME == Theme.DARK
    assert THEME_COLORS[Theme.LIGHT] == LIGHT_COLORS
    assert THEME_COLORS[Theme.DARK] == DARK_COLORS
    assert STATUS_THEME_COLORS[Theme.LIGHT] == LIGHT_STATUS_COLORS
    assert STATUS_THEME_COLORS[Theme.DARK] == DARK_STATUS_COLORS


def test_build_palette() -> None:
    palette = build_palette(DARK_COLORS)
    assert isinstance(palette, QPalette)
    assert palette.color(QPalette.ColorRole.Window).name().lower() == DARK_COLORS.window.lower()
    assert (
        palette.color(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText).name().lower()
        == DARK_COLORS.disabled_text.lower()
    )


def test_apply_theme_to_application(qapp) -> None:
    apply_theme(qapp, Theme.LIGHT)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == LIGHT_COLORS.window.lower()

    apply_theme(qapp, Theme.DARK)
    assert qapp.palette().color(QPalette.ColorRole.Window).name().lower() == DARK_COLORS.window.lower()


def test_get_status_colors() -> None:
    # Dark theme
    assert get_status_colors(StepStatus.IDLE, DARK_COLORS) == (DARK_COLORS.button, DARK_COLORS.button_text)
    assert get_status_colors(StepStatus.PENDING, DARK_COLORS) == (
        DARK_STATUS_COLORS.pending_bg,
        DARK_STATUS_COLORS.pending_text,
    )
    assert get_status_colors(StepStatus.RUNNING, DARK_COLORS) == (
        DARK_STATUS_COLORS.running_bg,
        DARK_STATUS_COLORS.running_text,
    )
    assert get_status_colors(StepStatus.COMPLETED, DARK_COLORS) == (
        DARK_STATUS_COLORS.completed_bg,
        DARK_STATUS_COLORS.completed_text,
    )

    # Light theme
    assert get_status_colors(StepStatus.IDLE, LIGHT_COLORS) == (LIGHT_COLORS.button, LIGHT_COLORS.button_text)
    assert get_status_colors(StepStatus.PENDING, LIGHT_COLORS) == (
        LIGHT_STATUS_COLORS.pending_bg,
        LIGHT_STATUS_COLORS.pending_text,
    )
    assert get_status_colors(StepStatus.RUNNING, LIGHT_COLORS) == (
        LIGHT_STATUS_COLORS.running_bg,
        LIGHT_STATUS_COLORS.running_text,
    )
    assert get_status_colors(StepStatus.COMPLETED, LIGHT_COLORS) == (
        LIGHT_STATUS_COLORS.completed_bg,
        LIGHT_STATUS_COLORS.completed_text,
    )


def test_scrollbar_and_scroll_area_stylesheet() -> None:
    scrollbar_qss = get_scrollbar_stylesheet(DARK_COLORS)
    assert "QScrollBar:vertical" in scrollbar_qss
    assert "QScrollBar:horizontal" in scrollbar_qss
    assert DARK_COLORS.placeholder_text in scrollbar_qss
    assert DARK_COLORS.highlight in scrollbar_qss

    scroll_area_qss = get_scroll_area_stylesheet(DARK_COLORS)
    assert names.MODERN_SCROLL_AREA in scroll_area_qss
    assert "background-color: transparent" in scroll_area_qss
    assert "QScrollBar:vertical" in scroll_area_qss


def test_accordion_stylesheets() -> None:
    header_qss = get_accordion_header_frame_stylesheet(DARK_COLORS, StepStatus.RUNNING)
    assert names.ACCORDION_HEADER_FRAME in header_qss
    assert DARK_STATUS_COLORS.running_bg in header_qss

    toggle_qss = get_accordion_toggle_button_stylesheet(DARK_COLORS, StepStatus.RUNNING)
    assert names.ACCORDION_TOGGLE_BUTTON in toggle_qss
    assert DARK_STATUS_COLORS.running_bg in toggle_qss
    assert "border-left" not in toggle_qss

    content_qss = get_accordion_content_area_stylesheet(DARK_COLORS)
    assert names.ACCORDION_CONTENT_AREA in content_qss
    assert DARK_COLORS.base in content_qss
    assert DARK_COLORS.alternate_base in content_qss

    play_qss = get_accordion_play_button_stylesheet(DARK_COLORS, StepStatus.RUNNING)
    assert names.PLAY_STAGE_BUTTON in play_qss
    assert "background-color: transparent" in play_qss


def test_right_panel_stylesheets() -> None:
    top_bar_qss = get_right_panel_top_bar_stylesheet(DARK_COLORS)
    assert names.RIGHT_PANEL_TOP_BAR in top_bar_qss
    assert names.TOGGLE_ALL_BUTTON in top_bar_qss
    assert DARK_COLORS.button in top_bar_qss

    stats_qss = get_bottom_stats_stylesheet(DARK_COLORS)
    assert names.BOTTOM_STATS_SECTION in stats_qss
    assert names.BOTTOM_STATS_HEADER in stats_qss
    assert names.BOTTOM_STATS_SUMMARY_LABEL in stats_qss
    assert names.BOTTOM_STATS_TOGGLE_BUTTON in stats_qss
    assert names.BOTTOM_STATS_DETAILS_FRAME in stats_qss
    assert names.BOTTOM_STATS_DETAILS_LABEL in stats_qss


def test_theme_styler_class() -> None:
    styler = ThemeStyler.for_theme(Theme.DARK)
    assert styler.colors == DARK_COLORS

    assert "QScrollBar:vertical" in styler.scrollbar()
    assert names.MODERN_SCROLL_AREA in styler.scroll_area()
    assert names.ACCORDION_HEADER_FRAME in styler.accordion_header_frame(StepStatus.PENDING)
    assert names.ACCORDION_TOGGLE_BUTTON in styler.accordion_toggle_button(StepStatus.PENDING)
    assert DARK_STATUS_COLORS.pending_bg in styler.accordion_toggle_button(StepStatus.PENDING)
    assert names.PLAY_STAGE_BUTTON in styler.accordion_play_button(StepStatus.PENDING)
    assert names.ACCORDION_CONTENT_AREA in styler.accordion_content_area()
    assert names.RIGHT_PANEL_TOP_BAR in styler.right_panel_top_bar()
    assert names.BOTTOM_STATS_SECTION in styler.bottom_stats()
    assert styler.status_colors(StepStatus.COMPLETED) == (
        DARK_STATUS_COLORS.completed_bg,
        DARK_STATUS_COLORS.completed_text,
    )


def test_component_styler_helpers(qtbot) -> None:
    btn = QPushButton()
    frame = QFrame()
    scroll = QScrollArea()
    widget = QWidget()
    qtbot.addWidget(btn)
    qtbot.addWidget(frame)
    qtbot.addWidget(scroll)
    qtbot.addWidget(widget)

    AccordionStyler.apply(btn, frame, LIGHT_COLORS, StepStatus.COMPLETED)
    assert LIGHT_STATUS_COLORS.completed_bg in btn.styleSheet()
    assert LIGHT_COLORS.base in frame.styleSheet()

    ScrollAreaStyler.apply(scroll, LIGHT_COLORS)
    assert names.MODERN_SCROLL_AREA in scroll.styleSheet()

    RightPanelStyler.apply_bottom_stats(widget, LIGHT_COLORS)
    assert names.BOTTOM_STATS_SECTION in widget.styleSheet()
