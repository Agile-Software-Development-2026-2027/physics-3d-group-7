"""
Unit tests for the AccordionSection, ModernScrollArea, and AccordionDemo components.
"""

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget

from apkit4d.gui.constants import colors as gui_colors
from apkit4d.gui.constants import names
from apkit4d.gui.models.pipeline_model import StepStatus
from apkit4d.gui.shared.components.accordion import (
    AccordionDemo,
    AccordionSection,
)
from apkit4d.gui.shared.components.scroll_area import (
    ModernScrollArea,
    get_scrollbar_stylesheet,
)
from apkit4d.gui.theme.themes import DARK_COLORS, LIGHT_COLORS, Theme


def test_accordion_section_init(qtbot) -> None:
    section = AccordionSection("Test Section")
    qtbot.addWidget(section)

    assert section.title == "Test Section"
    assert not section.is_expanded()
    assert section.status == StepStatus.IDLE
    assert section.toggle_button.text() == "▼ Test Section"
    assert section.toggle_button.objectName() == names.ACCORDION_TOGGLE_BUTTON
    assert section.content_area.objectName() == names.ACCORDION_CONTENT_AREA
    assert section.content_area.maximumHeight() == 0


def test_accordion_section_title_setter(qtbot) -> None:
    section = AccordionSection("Initial")
    qtbot.addWidget(section)

    section.title = "Updated"
    assert section.title == "Updated"
    assert section.toggle_button.text() == "▼ Updated"


def test_accordion_section_add_widget_and_qlabel_styling(qtbot) -> None:
    section = AccordionSection("Widgets")
    qtbot.addWidget(section)

    label = QLabel("Plain Label")
    button = QPushButton("Action")
    section.add_widget(label)
    section.add_widget(button)

    assert section.content_layout.count() == 2
    # Ensure content_area has the isolated object name selector
    assert f"QFrame#{names.ACCORDION_CONTENT_AREA}" in section.content_area.styleSheet()
    assert "QLabel" in section.content_area.styleSheet()
    assert label.objectName() != names.ACCORDION_CONTENT_AREA


def test_accordion_section_expand_and_collapse(qtbot) -> None:
    section = AccordionSection("Expand Test")
    qtbot.addWidget(section)

    label = QLabel("Content inside")
    section.add_widget(label)

    # Expand without animation for instant state check
    section.set_expanded(True, animate=False)
    assert section.is_expanded()
    assert section.toggle_button.text() == "▲ Expand Test"
    assert section.content_area.maximumHeight() > 0

    # Collapse without animation
    section.set_expanded(False, animate=False)
    assert not section.is_expanded()
    assert section.toggle_button.text() == "▼ Expand Test"
    assert section.content_area.maximumHeight() == 0

    # Expand with animation
    section.set_expanded(True, animate=True)
    assert section.is_expanded()
    assert section.toggle_button.text() == "▲ Expand Test"

    # Redundant set_expanded should return early
    section.set_expanded(True, animate=True)
    assert section.is_expanded()

    # Collapse with animation
    section.set_expanded(False, animate=True)
    assert not section.is_expanded()
    assert section.toggle_button.text() == "▼ Expand Test"


def test_accordion_section_toggle_animation(qtbot) -> None:
    section = AccordionSection("Anim Test")
    qtbot.addWidget(section)
    section.add_widget(QLabel("Anim Content"))

    # Trigger animated toggle
    section.toggle_button.click()
    assert section.is_expanded()
    assert section.toggle_button.text() == "▲ Anim Test"

    section.toggle_button.click()
    assert not section.is_expanded()
    assert section.toggle_button.text() == "▼ Anim Test"


def test_accordion_section_theme_application(qtbot) -> None:
    section = AccordionSection("Theme Section")
    qtbot.addWidget(section)

    # Apply Dark
    section.apply_theme(DARK_COLORS)
    assert DARK_COLORS.button in section.toggle_button.styleSheet()
    assert DARK_COLORS.base in section.content_area.styleSheet()

    # Apply Light
    section.apply_theme(LIGHT_COLORS)
    assert LIGHT_COLORS.button in section.toggle_button.styleSheet()
    assert LIGHT_COLORS.base in section.content_area.styleSheet()


def test_accordion_section_status_colors(qtbot) -> None:
    section = AccordionSection("Status Section")
    qtbot.addWidget(section)

    # Initially IDLE
    assert section.status == StepStatus.IDLE

    # Transition to PENDING (Muted Blue) in dark theme
    section.apply_theme(DARK_COLORS)
    section.set_status(StepStatus.PENDING)
    assert section.status == StepStatus.PENDING
    assert gui_colors.DARK_STATUS_PENDING_BG in section.toggle_button.styleSheet()
    # Confirm no left accent border
    assert "border-left" not in section.toggle_button.styleSheet()

    # Same status call is a no-op
    section.set_status(StepStatus.PENDING)
    assert section.status == StepStatus.PENDING

    # Transition to RUNNING (Muted Orange)
    section.set_status(StepStatus.RUNNING)
    assert section.status == StepStatus.RUNNING
    assert gui_colors.DARK_STATUS_RUNNING_BG in section.toggle_button.styleSheet()
    assert "border-left" not in section.toggle_button.styleSheet()

    # Transition to COMPLETED (Muted Green)
    section.set_status(StepStatus.COMPLETED)
    assert section.status == StepStatus.COMPLETED
    assert gui_colors.DARK_STATUS_COMPLETED_BG in section.toggle_button.styleSheet()
    assert "border-left" not in section.toggle_button.styleSheet()

    # Switch to Light theme while COMPLETED
    section.apply_theme(LIGHT_COLORS)
    assert gui_colors.LIGHT_STATUS_COMPLETED_BG in section.toggle_button.styleSheet()
    assert gui_colors.LIGHT_STATUS_COMPLETED_TEXT in section.toggle_button.styleSheet()

    # Back to IDLE
    section.set_status(StepStatus.IDLE)
    assert section.status == StepStatus.IDLE
    assert LIGHT_COLORS.button in section.toggle_button.styleSheet()


def test_modern_scrollbar_stylesheet() -> None:
    qss = get_scrollbar_stylesheet(DARK_COLORS)
    assert "QScrollBar:vertical" in qss
    assert "QScrollBar:horizontal" in qss
    assert DARK_COLORS.placeholder_text in qss
    assert DARK_COLORS.highlight in qss


def test_modern_scroll_area(qtbot) -> None:
    scroll_area = ModernScrollArea()
    qtbot.addWidget(scroll_area)

    content = QWidget()
    scroll_area.setWidget(content)

    assert scroll_area.frameShape() == QFrame.Shape.NoFrame
    assert scroll_area.widgetResizable()
    assert scroll_area.objectName() == names.MODERN_SCROLL_AREA

    scroll_area.apply_theme(LIGHT_COLORS)
    assert LIGHT_COLORS.placeholder_text in scroll_area.styleSheet()


def test_accordion_demo(qtbot) -> None:
    demo = AccordionDemo()
    qtbot.addWidget(demo)

    assert demo.active_theme == Theme.DARK
    assert len(demo._sections) == 9

    # Toggle theme to light
    demo.toggle_theme()
    assert demo.active_theme == Theme.LIGHT

    # Set explicit theme
    demo.set_theme(Theme.DARK)
    assert demo.active_theme == Theme.DARK
