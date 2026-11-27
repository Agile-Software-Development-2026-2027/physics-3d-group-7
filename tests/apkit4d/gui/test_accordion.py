"""
Unit tests for the AccordionSection, ModernScrollArea, and AccordionDemo components.
"""

from PySide6.QtWidgets import QFrame, QLabel, QPushButton, QWidget

from apkit4d.gui.constants import names
from apkit4d.gui.models.pipeline_model import StepStatus
from apkit4d.gui.theme import apply_theme
from apkit4d.gui.theme.themes import (
    DARK_COLORS,
    DARK_STATUS_COLORS,
    LIGHT_COLORS,
    LIGHT_STATUS_COLORS,
    Theme,
)
from apkit4d.gui.views.widgets.accordion import (
    AccordionDemo,
    AccordionSection,
)
from apkit4d.gui.views.widgets.scroll_area import ModernScrollArea
from tests.apkit4d.gui.helper import painted_color


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


def test_accordion_section_theme_application(qapp, qtbot) -> None:
    section = AccordionSection("Theme Section")
    qtbot.addWidget(section)
    section.show()
    header = section.header_frame

    # the stylesheet of the application paints the section: switching the theme repaints it
    apply_theme(qapp, Theme.DARK)
    assert painted_color(header, header.width() - 3, header.height() // 2) == DARK_COLORS.button

    apply_theme(qapp, Theme.LIGHT)
    assert painted_color(header, header.width() - 3, header.height() // 2) == LIGHT_COLORS.button


def test_accordion_section_status_colors(qapp, qtbot) -> None:
    apply_theme(qapp, Theme.DARK)
    section = AccordionSection("Status Section")
    qtbot.addWidget(section)
    section.show()
    header = section.header_frame

    def header_color() -> str:
        return painted_color(header, header.width() - 3, header.height() // 2)

    # Initially IDLE
    assert section.status == StepStatus.IDLE
    assert header.property("status") == StepStatus.IDLE.value

    # Transition to PENDING (Muted Blue) in dark theme
    section.set_status(StepStatus.PENDING)
    assert section.status == StepStatus.PENDING
    assert header.property("status") == StepStatus.PENDING.value
    assert section.toggle_button.property("status") == StepStatus.PENDING.value
    assert header_color() == DARK_STATUS_COLORS.pending_bg

    # Same status call is a no-op
    section.set_status(StepStatus.PENDING)
    assert section.status == StepStatus.PENDING

    # Transition to RUNNING (Muted Orange)
    section.set_status(StepStatus.RUNNING)
    assert header_color() == DARK_STATUS_COLORS.running_bg

    # Transition to COMPLETED (Muted Green)
    section.set_status(StepStatus.COMPLETED)
    assert header_color() == DARK_STATUS_COLORS.completed_bg

    # Switch to Light theme while COMPLETED
    apply_theme(qapp, Theme.LIGHT)
    assert header_color() == LIGHT_STATUS_COLORS.completed_bg

    # Back to IDLE
    section.set_status(StepStatus.IDLE)
    assert header_color() == LIGHT_COLORS.button


def test_expanded_section_header_joins_its_content(qtbot) -> None:
    section = AccordionSection("Expand Test")
    qtbot.addWidget(section)
    assert section.header_frame.property("expanded") is False

    section.set_expanded(True, animate=False)
    assert section.header_frame.property("expanded") is True

    section.toggle_button.click()
    assert section.header_frame.property("expanded") is False


def test_play_button_follows_the_status_of_the_section(qtbot) -> None:
    section = AccordionSection("Play Test")
    qtbot.addWidget(section)
    section.set_status(StepStatus.RUNNING)
    play_btn = section.enable_play_button()
    assert play_btn.property("status") == StepStatus.RUNNING.value

    section.set_status(StepStatus.COMPLETED)
    assert play_btn.property("status") == StepStatus.COMPLETED.value


def test_modern_scroll_area(qtbot) -> None:
    scroll_area = ModernScrollArea()
    qtbot.addWidget(scroll_area)

    content = QWidget()
    scroll_area.setWidget(content)

    assert scroll_area.frameShape() == QFrame.Shape.NoFrame
    assert scroll_area.widgetResizable()
    assert scroll_area.objectName() == names.MODERN_SCROLL_AREA


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


def test_accordion_section_configurable_header_actions(qtbot) -> None:
    section = AccordionSection("Actions Test")
    qtbot.addWidget(section)

    assert section.play_button is None
    assert section.right_widget is None

    # Enable play button with callback
    callback_calls = []
    play_btn = section.enable_play_button(callback=lambda: callback_calls.append("play"))
    assert play_btn is not None
    assert section.play_button is play_btn
    assert section.right_widget is play_btn
    assert play_btn.parent() is section.header_frame

    # Clicking play button triggers signal and callback without toggling expansion
    with qtbot.waitSignal(section.play_clicked):
        play_btn.click()
    assert callback_calls == ["play"]
    assert not section.is_expanded()

    # Clicking toggle button toggles expansion without calling play callback
    section.toggle_button.click()
    assert section.is_expanded()
    assert callback_calls == ["play"]

    # Re-calling enable_play_button is idempotent
    assert section.enable_play_button() is play_btn

    # Add custom action button with custom callback
    custom_calls = []
    custom_btn = section.add_header_action(
        text="⚙",
        callback=lambda: custom_calls.append("gear"),
        tooltip="Settings",
        object_name="custom_gear_btn",
    )
    assert section.right_widget is custom_btn
    assert section.play_button is None
    assert custom_btn.objectName() == "custom_gear_btn"
    assert custom_btn.toolTip() == "Settings"

    custom_btn.click()
    assert custom_calls == ["gear"]

    # Set custom arbitrary QWidget
    custom_widget = QLabel("STATUS")
    section.set_right_widget(custom_widget)
    assert section.right_widget is custom_widget

    # Clear right widget
    section.set_right_widget(None)
    assert section.right_widget is None


def test_expanded_section_follows_the_height_of_its_content(qtbot) -> None:
    section = AccordionSection("Growing")
    qtbot.addWidget(section)
    section.add_widget(QLabel("First row"))
    section.set_expanded(True, animate=False)
    section.show()
    height = section.content_area.sizeHint().height()

    section.add_widget(QLabel("Second row"))  # added after the section is open
    qtbot.waitUntil(lambda: section.content_area.height() > height)

    section.set_expanded(False, animate=False)
    assert section.content_area.maximumHeight() == 0


def test_animated_expansion_releases_the_height_at_the_end(qtbot) -> None:
    section = AccordionSection("Animated")
    qtbot.addWidget(section)
    section.add_widget(QLabel("Content"))
    section.show()
    with qtbot.waitSignal(section.anim_group.finished):
        section.set_expanded(True, animate=True)
    assert section.content_area.maximumHeight() > section.content_area.sizeHint().height()
