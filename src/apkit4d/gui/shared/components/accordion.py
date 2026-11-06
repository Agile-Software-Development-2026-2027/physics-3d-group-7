"""
Accordion widget.

Provides collapsible accordion sections with smooth height animations.
"""

import sys
from collections.abc import Callable

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.gui.models.pipeline_model import StepStatus
from apkit4d.gui.shared.components.scroll_area import ModernScrollArea
from apkit4d.gui.theme import (
    DEFAULT_THEME,
    THEME_COLORS,
    AccordionStyler,
    Theme,
    ThemeColors,
    apply_theme,
)

__all__ = ["AccordionSection"]


class AccordionSection(QWidget):
    """
    Collapsible section with an animated content container and customizable header actions.

    Args:
        title: Title displayed on the header toggle button.
        parent: Optional parent widget.
        show_play_button: Whether to display a play action button on the header.
        right_widget: Optional custom widget placed on the right portion of the header.
    """

    play_clicked = Signal()

    def __init__(
        self,
        title: str = "",
        parent: QWidget | None = None,
        show_play_button: bool = False,
        right_widget: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._title: str = title
        self._status: StepStatus = StepStatus.IDLE
        self._theme_colors: ThemeColors = THEME_COLORS[DEFAULT_THEME]
        self._right_widget: QWidget | None = None
        self._play_button: QPushButton | None = None

        # Primary layouts
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Header Container Frame
        self.header_frame = QFrame(self)
        self.header_frame.setObjectName(names.ACCORDION_HEADER_FRAME)
        self.header_layout = QHBoxLayout(self.header_frame)
        self.header_layout.setContentsMargins(0, 0, 6, 0)
        self.header_layout.setSpacing(4)

        # Header Button (Toggles collapse)
        self.toggle_button = QPushButton(self.header_frame)
        self.toggle_button.setObjectName(names.ACCORDION_TOGGLE_BUTTON)
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self._update_toggle_button_text(False)
        self.header_layout.addWidget(self.toggle_button, stretch=1)

        # Content Container
        self.content_area = QFrame(self)
        self.content_area.setObjectName(names.ACCORDION_CONTENT_AREA)
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)

        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_area.setMaximumHeight(0)

        # Add to main section layout
        self.main_layout.addWidget(self.header_frame)
        self.main_layout.addWidget(self.content_area)

        # Smooth Animation Setup
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(300)
        self.toggle_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.toggle_animation)

        # Connect the click signal
        self.toggle_button.clicked.connect(self.on_toggle)

        # Install custom right widget or play button if requested
        if right_widget is not None:
            self.set_right_widget(right_widget)
        elif show_play_button:
            self.enable_play_button()

        # Initialize with default theme
        self.apply_theme(THEME_COLORS[DEFAULT_THEME])

    @property
    def play_button(self) -> QPushButton | None:
        """The play button on the right portion of the header, if enabled."""
        return self._play_button

    @property
    def right_widget(self) -> QWidget | None:
        """The custom widget placed on the right portion of the header, if any."""
        return self._right_widget

    def set_right_widget(self, widget: QWidget | None) -> None:
        """
        Set or clear the widget placed on the right portion of the accordion header.

        Args:
            widget: A QWidget to display on the right, or None to clear.
        """
        if self._right_widget is not None:
            self.header_layout.removeWidget(self._right_widget)
            if self._right_widget is not widget:
                self._right_widget.setParent(None)
            if self._right_widget is self._play_button:
                self._play_button = None
            self._right_widget = None

        if widget is not None:
            self._right_widget = widget
            self.header_layout.addWidget(widget)

    def add_header_action(
        self,
        text: str,
        callback: Callable[[], None] | None = None,
        tooltip: str = "",
        object_name: str = "",
    ) -> QPushButton:
        """
        Add a customizable action button on the right portion of the accordion header.

        Args:
            text: Text or icon symbol displayed on the button.
            callback: Optional callback invoked when the button is clicked.
            tooltip: Optional tooltip for the button.
            object_name: Optional Qt object name.

        Returns:
            The created action QPushButton.
        """
        btn = QPushButton(text, self.header_frame)
        btn.setObjectName(object_name or names.PLAY_STAGE_BUTTON)
        btn.setToolTip(tooltip)
        btn.setFixedSize(26, 26)
        if callback is not None:
            btn.clicked.connect(lambda _=False, cb=callback: cb())
        self.set_right_widget(btn)
        if hasattr(self, "_theme_colors"):
            btn.setStyleSheet(AccordionStyler.play_button_stylesheet(self._theme_colors, self._status))
        return btn

    def enable_play_button(
        self,
        callback: Callable[[], None] | None = None,
        tooltip: str = "",
    ) -> QPushButton:
        """
        Create and insert the play button on the right portion of the accordion header.

        Args:
            callback: Optional callback invoked when the play button is clicked.
            tooltip: Optional tooltip for the button.

        Returns:
            The created QPushButton.
        """
        if self._play_button is not None:
            return self._play_button

        btn = self.add_header_action(
            text=texts.BUTTON_PLAY_STAGE,
            callback=callback,
            tooltip=tooltip or texts.TOOLTIP_PLAY_STAGE,
            object_name=names.PLAY_STAGE_BUTTON,
        )
        btn.clicked.connect(self.play_clicked.emit)
        self._play_button = btn
        return btn

    @property
    def status(self) -> StepStatus:
        """The current step status of the section."""
        return self._status

    def set_status(self, status: StepStatus) -> None:
        """
        Update the execution status of this section and refresh its visual styling.

        Args:
            status: The new StepStatus (IDLE, PENDING, RUNNING, COMPLETED).
        """
        if self._status == status:
            return
        self._status = status
        self.apply_theme(self._theme_colors)

    @property
    def title(self) -> str:
        """The section title."""
        return self._title

    @title.setter
    def title(self, value: str) -> None:
        self._title = value
        self._update_toggle_button_text(self.toggle_button.isChecked())

    def _update_toggle_button_text(self, checked: bool) -> None:
        """Update toggle button arrow and title text."""
        arrow = texts.STATS_ARROW_COLLAPSED if checked else texts.STATS_ARROW_EXPANDED
        self.toggle_button.setText(f"{arrow} {self._title}")

    def add_widget(self, widget: QWidget) -> None:
        """
        Add a child widget inside the accordion content area.

        Args:
            widget: Widget to add inside the section.
        """
        self.content_layout.addWidget(widget)

    def is_expanded(self) -> bool:
        """Return True if the section is currently expanded."""
        return self.toggle_button.isChecked()

    def _update_header_style(self) -> None:
        """Refresh header frame and toggle button styles for expanded/collapsed state."""
        if hasattr(self, "_theme_colors"):
            is_expanded = self.toggle_button.isChecked()
            self.header_frame.setStyleSheet(
                AccordionStyler.header_frame_stylesheet(self._theme_colors, self._status, is_expanded)
            )
            self.toggle_button.setStyleSheet(
                AccordionStyler.toggle_button_stylesheet(self._theme_colors, self._status, is_expanded)
            )
            if self._play_button is not None:
                self._play_button.setStyleSheet(
                    AccordionStyler.play_button_stylesheet(self._theme_colors, self._status)
                )

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        """
        Set the expanded state of the section.

        Args:
            expanded: True to expand, False to collapse.
            animate: Whether to animate the transition.
        """
        if self.toggle_button.isChecked() == expanded:
            return
        self.toggle_button.setChecked(expanded)
        if animate:
            self.on_toggle(expanded)
        else:
            self._update_toggle_button_text(expanded)
            self._update_header_style()
            content_height = self.content_area.sizeHint().height()
            target_height = content_height if expanded else 0
            self.anim_group.stop()
            self.content_area.setMaximumHeight(target_height)

    def on_toggle(self, checked: bool) -> None:
        """
        Handle header button toggle and run expanding/collapsing animation.

        Args:
            checked: True if expanding, False if collapsing.
        """
        self._update_toggle_button_text(checked)
        self._update_header_style()

        content_height = self.content_area.sizeHint().height()
        start_height = self.content_area.maximumHeight()
        end_height = content_height if checked else 0

        self.anim_group.stop()
        self.toggle_animation.setStartValue(start_height)
        self.toggle_animation.setEndValue(end_height)
        self.anim_group.start()

    def apply_theme(self, colors: ThemeColors) -> None:
        """
        Apply theme colors to header button, content area, and text.
        Maintains active step status colors across theme changes.

        Args:
            colors: Colors of the active theme.
        """
        self._theme_colors = colors
        is_expanded = self.toggle_button.isChecked()
        AccordionStyler.apply(
            self.toggle_button,
            self.content_area,
            colors,
            self._status,
            self._play_button,
            self.header_frame,
            is_expanded,
        )


class AccordionDemo(QWidget):
    """
    Demo window showcasing the accordion layout and theme connectivity.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PySide6 Accordion Layout")
        self.resize(420, 560)

        self._active_theme: Theme = DEFAULT_THEME
        self._sections: list[AccordionSection] = []

        # Window main layout
        window_layout = QVBoxLayout(self)
        window_layout.setContentsMargins(12, 12, 12, 12)
        window_layout.setSpacing(10)

        # Theme switcher toolbar
        toolbar_layout = QHBoxLayout()
        self._theme_label = QLabel(f"Active Theme: {self._active_theme.value.title()}")
        self._theme_toggle_btn = QPushButton(texts.BUTTON_THEME)
        self._theme_toggle_btn.clicked.connect(self.toggle_theme)

        toolbar_layout.addWidget(self._theme_label)
        toolbar_layout.addStretch()
        toolbar_layout.addWidget(self._theme_toggle_btn)
        window_layout.addLayout(toolbar_layout)

        # Scroll area with modern scrollbar
        self.scroll_area = ModernScrollArea()
        self.scroll_area.setObjectName(names.MODERN_SCROLL_AREA)

        scroll_content = QWidget()
        scroll_content.setObjectName(names.SCROLL_CONTENT)
        self.accordion_layout = QVBoxLayout(scroll_content)
        self.accordion_layout.setContentsMargins(5, 5, 5, 5)
        self.accordion_layout.setSpacing(6)

        # Sample sections
        for i in range(1, 10):
            section = AccordionSection(f"Section {i}")
            for j in range(1, 4):
                section.add_widget(QLabel(f"Item {j} in Section {i}"))
            self.accordion_layout.addWidget(section)
            self._sections.append(section)

        # Add a stretch at the bottom to force items up when collapsed
        self.accordion_layout.addStretch()

        self.scroll_area.setWidget(scroll_content)
        window_layout.addWidget(self.scroll_area)

        self.apply_theme_colors(THEME_COLORS[self._active_theme])

    @property
    def active_theme(self) -> Theme:
        """The currently displayed theme in the demo."""
        return self._active_theme

    def toggle_theme(self) -> None:
        """Toggle between Light and Dark themes."""
        self.set_theme(self._active_theme.opposite)

    def set_theme(self, theme: Theme) -> None:
        """
        Switch application theme and re-style demo components.

        Args:
            theme: Target theme to apply.
        """
        self._active_theme = theme
        app = QApplication.instance()
        if isinstance(app, QApplication):
            apply_theme(app, theme)

        colors = THEME_COLORS[theme]
        self._theme_label.setText(f"Active Theme: {theme.value.title()}")
        self.apply_theme_colors(colors)

    def apply_theme_colors(self, colors: ThemeColors) -> None:
        """
        Update demo widget styles with the given theme colors.

        Args:
            colors: Colors of the active theme.
        """
        self.setStyleSheet(f"background-color: {colors.window}; color: {colors.window_text};")
        self.scroll_area.apply_theme(colors)
        for section in self._sections:
            section.apply_theme(colors)


if __name__ == "__main__":
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        app = QApplication(sys.argv)
    apply_theme(app, DEFAULT_THEME)
    demo = AccordionDemo()
    demo.show()
    sys.exit(app.exec())
