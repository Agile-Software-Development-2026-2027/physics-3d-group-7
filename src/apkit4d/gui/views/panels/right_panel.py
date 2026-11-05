"""
Right column of the main window.

Houses the top control bar (Toggle All), the 5 consolidated
pipeline accordion stages with execution triggers, and a collapsible bottom
statistics and diagnostics section.
"""

from typing import Any

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.shared.components.scroll_area import ModernScrollArea
from apkit4d.gui.theme import (
    DEFAULT_THEME,
    THEME_COLORS,
    RightPanelStyler,
    Theme,
    ThemeColors,
)
from apkit4d.gui.views.panels.side_panel import SidePanel

__all__ = ["BottomStatsSection", "RightPanel"]


class BottomStatsSection(QFrame):
    """
    Collapsible statistics and status panel docked at the bottom of the right panel.

    Supports two display states:
    - Collapsed: displays concise summary information (e.g., 'Working: 15%').
    - Expanded: unfolds to reveal comprehensive diagnostic or metric details.

    Args:
        parent: Optional parent widget.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(names.BOTTOM_STATS_SECTION)
        self._is_expanded: bool = False

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)
        self._main_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # Summary header (always visible)
        self._header = QFrame(self)
        self._header.setObjectName(names.BOTTOM_STATS_HEADER)
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(6)

        self._summary_label = QLabel(texts.STATS_INITIAL_SUMMARY)
        self._summary_label.setObjectName(names.BOTTOM_STATS_SUMMARY_LABEL)

        self._toggle_btn = QPushButton(texts.STATS_ARROW_COLLAPSED)
        self._toggle_btn.setObjectName(names.BOTTOM_STATS_TOGGLE_BUTTON)
        self._toggle_btn.setFixedSize(24, 20)
        self._toggle_btn.setToolTip(texts.TOOLTIP_STATS_TOGGLE)
        self._toggle_btn.clicked.connect(lambda: self.toggle(animate=True))

        header_layout.addWidget(self._summary_label, stretch=1)
        header_layout.addWidget(self._toggle_btn)

        # Details container (collapsible)
        self._details_frame = QFrame(self)
        self._details_frame.setObjectName(names.BOTTOM_STATS_DETAILS_FRAME)
        self._details_layout = QVBoxLayout(self._details_frame)
        self._details_layout.setContentsMargins(8, 6, 8, 6)
        self._details_layout.setSpacing(4)

        self._details_label = QLabel(texts.STATS_INITIAL_DETAILS)
        self._details_label.setObjectName(names.BOTTOM_STATS_DETAILS_LABEL)
        self._details_label.setWordWrap(True)
        self._details_layout.addWidget(self._details_label)

        # Start collapsed with maximumHeight = 0
        self._details_frame.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._details_frame.setMaximumHeight(0)

        self._main_layout.addWidget(self._header)
        self._main_layout.addWidget(self._details_frame)

        # Smooth animation setup
        self._animation = QPropertyAnimation(self._details_frame, b"maximumHeight")
        self._animation.setDuration(250)
        self._animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

    @property
    def summary_label(self) -> QLabel:
        """Label displaying the short summary in the header."""
        return self._summary_label

    @property
    def details_label(self) -> QLabel:
        """Label displaying the detailed statistics."""
        return self._details_label

    def is_expanded(self) -> bool:
        """Return True if details are currently expanded."""
        return self._is_expanded

    def set_summary(self, text: str) -> None:
        """Update the summary text."""
        self._summary_label.setText(text)

    def set_details(self, text: str) -> None:
        """Update the detailed stats text."""
        self._details_label.setText(text)

    def set_expanded(self, expanded: bool, animate: bool = True) -> None:
        """
        Set whether details are expanded or collapsed.

        Args:
            expanded: True to show details, False to collapse.
            animate: Whether to animate the transition.
        """
        if self._is_expanded == expanded:
            return
        self._is_expanded = expanded
        self._toggle_btn.setText(texts.STATS_ARROW_EXPANDED if expanded else texts.STATS_ARROW_COLLAPSED)

        target_height = self._details_layout.sizeHint().height() + 12 if expanded else 0

        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._details_frame.maximumHeight())
            self._animation.setEndValue(target_height)
            self._animation.start()
        else:
            self._animation.stop()
            self._details_frame.setMaximumHeight(target_height)

    def toggle(self, animate: bool = True) -> None:
        """Toggle between collapsed and expanded states."""
        self.set_expanded(not self._is_expanded, animate=animate)

    def apply_theme(self, colors: ThemeColors) -> None:
        """Apply theme colors to header, labels, borders, and details frame."""
        RightPanelStyler.apply_bottom_stats(self, colors)


class RightPanel(SidePanel):
    """
    Right column of the main window.

    Houses:
    - Top bar: action controls ('Toggle All').
    - Middle: 5 consolidated pipeline stages, each equipped with an Execute button.
    - Bottom: collapsible statistics panel with summary and detailed states.

    Signals:
        execute_stage_requested: Emitted with (PipelineStep) when an execute button is clicked.
        step_param_changed: Emitted with (step_name, param_name, value) when a setting changes.
    """

    execute_stage_requested = Signal(object)
    step_param_changed = Signal(str, str, object)

    def __init__(self) -> None:
        super().__init__(names.RIGHT_PANEL)
        self._theme: Theme = DEFAULT_THEME
        self._sections: list[AccordionSection] = []
        self._stage_sections: dict[str, AccordionSection] = {}
        self._execute_buttons: dict[PipelineStep, QPushButton] = {}

        # Remove the inherited bottom stretch
        while self._layout.count() > 0:
            self._layout.takeAt(0)

        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        # Top Controls Bar
        self.top_bar = QFrame(self)
        self.top_bar.setObjectName(names.RIGHT_PANEL_TOP_BAR)
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(6)

        self.toggle_all_btn = QPushButton(texts.BUTTON_TOGGLE_ALL, self.top_bar)
        self.toggle_all_btn.setObjectName(names.TOGGLE_ALL_BUTTON)
        self.toggle_all_btn.setToolTip(texts.TOOLTIP_TOGGLE_ALL)
        self.toggle_all_btn.clicked.connect(self.toggle_all)

        top_layout.addWidget(self.toggle_all_btn)

        # Middle Scroll Area with Accordion Sections
        self.scroll_area = ModernScrollArea(self)
        self.scroll_area.setObjectName(names.MODERN_SCROLL_AREA)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._scroll_content = QWidget()
        self._scroll_content.setObjectName(names.SCROLL_CONTENT)
        self.accordion_layout = QVBoxLayout(self._scroll_content)
        self.accordion_layout.setContentsMargins(4, 4, 4, 4)
        self.accordion_layout.setSpacing(6)

        self.accordion_layout.addStretch()
        self.scroll_area.setWidget(self._scroll_content)

        # Bottom Stats Section
        self._bottom_stats = BottomStatsSection(self)

        self._layout.addWidget(self.top_bar)
        self._layout.addWidget(self.scroll_area, stretch=1)
        self._layout.addWidget(self._bottom_stats)

        # Build the 5 consolidated pipeline stages
        self._build_pipeline_stages()
        self.set_theme(DEFAULT_THEME)

    @property
    def theme(self) -> Theme:
        """The currently applied theme."""
        return self._theme

    @property
    def sections(self) -> list[AccordionSection]:
        """List of active accordion sections."""
        return list(self._sections)

    @property
    def bottom_stats(self) -> BottomStatsSection:
        """The collapsible statistics section at the bottom."""
        return self._bottom_stats

    def get_section(self, step: str | PipelineStep) -> AccordionSection | None:
        """
        Return the AccordionSection associated with `step`.

        Args:
            step: Step identifier or enum member.
        """
        key = step.value if isinstance(step, PipelineStep) else str(step)
        return self._stage_sections.get(key)

    def get_execute_button(self, step: str | PipelineStep) -> QPushButton | None:
        """
        Return the Execute QPushButton associated with `step`.

        Args:
            step: Step identifier or enum member.
        """
        enum_step = PipelineStep(step) if isinstance(step, str) else step
        return self._execute_buttons.get(enum_step)

    def set_step_status(self, step: str | PipelineStep, status: StepStatus) -> None:
        """
        Update the status and visual styling of a pipeline section.

        Args:
            step: The step identifier.
            status: New StepStatus (IDLE, PENDING, RUNNING, COMPLETED).
        """
        section = self.get_section(step)
        if section is not None:
            section.set_status(status)

    def toggle_all(self) -> None:
        """Toggle all accordion sections."""
        all_expanded = bool(self._sections) and all(s.is_expanded() for s in self._sections)
        self.set_all_expanded(not all_expanded)

    def expand_all(self) -> None:
        """Expand all accordion sections."""
        self.set_all_expanded(True)

    def collapse_all(self) -> None:
        """Collapse all accordion sections."""
        self.set_all_expanded(False)

    def set_all_expanded(self, expanded: bool, animate: bool = True) -> None:
        """Set expanded state on all accordion sections."""
        for section in self._sections:
            section.set_expanded(expanded, animate=animate)

    def set_stats_summary(self, text: str) -> None:
        """Update summary text in bottom stats bar."""
        self._bottom_stats.set_summary(text)

    def set_stats_details(self, text: str) -> None:
        """Update detailed text in bottom stats bar."""
        self._bottom_stats.set_details(text)

    def toggle_stats(self, animate: bool = True) -> None:
        """Toggle bottom stats expansion state."""
        self._bottom_stats.toggle(animate=animate)

    def add_section(self, section: AccordionSection) -> None:
        """Add an accordion section above the bottom stretch."""
        self._sections.append(section)
        stretch_index = max(self.accordion_layout.count() - 1, 0)
        self.accordion_layout.insertWidget(stretch_index, section)
        section.apply_theme(THEME_COLORS[self._theme])

    def remove_section(self, section: AccordionSection) -> None:
        """Remove an accordion section from the panel."""
        if section in self._sections:
            self._sections.remove(section)
            self.accordion_layout.removeWidget(section)
            section.setParent(None)
            section.deleteLater()

    def clear_sections(self) -> None:
        """Remove all accordion sections from the panel."""
        self._stage_sections.clear()
        self._execute_buttons.clear()
        for section in list(self._sections):
            self.remove_section(section)

    def add_control(self, widget: QWidget) -> None:
        """Add a generic control widget inside the scrollable layout."""
        stretch_index = max(self.accordion_layout.count() - 1, 0)
        self.accordion_layout.insertWidget(stretch_index, widget)

    def set_theme(self, theme: Theme) -> None:
        """Apply theme to all right panel components."""
        self._theme = theme
        self.apply_theme(THEME_COLORS[theme])

    def apply_theme(self, colors: ThemeColors) -> None:
        """Apply theme colors to all components."""
        self._style_top_bar(colors)
        self.scroll_area.apply_theme(colors)
        for section in self._sections:
            section.apply_theme(colors)
        self._bottom_stats.apply_theme(colors)

    def _style_top_bar(self, colors: ThemeColors) -> None:
        """Style the top control bar with the active theme colors."""
        self.top_bar.setStyleSheet(RightPanelStyler.top_bar_stylesheet(colors))

    def _build_pipeline_stages(self) -> None:
        """
        Construct the 5 consolidated pipeline stages, each equipped with an Execute button.
        """
        stage_definitions: tuple[tuple[PipelineStep, str], ...] = (
            (PipelineStep.ROI, texts.STAGE_TITLE_ROI),
            (PipelineStep.PREPROCESSING, texts.STAGE_TITLE_PREPROCESSING),
            (PipelineStep.DETECTION, texts.STAGE_TITLE_DETECTION),
            (PipelineStep.TRACKING, texts.STAGE_TITLE_TRACKING),
            (PipelineStep.BATCH, texts.STAGE_TITLE_BATCH),
        )

        for step, title in stage_definitions:
            sec = AccordionSection(title)
            execute_btn = QPushButton(texts.BUTTON_EXECUTE)
            execute_btn.setObjectName(names.EXECUTE_STAGE_BUTTON)
            execute_btn.setToolTip(texts.TOOLTIP_EXECUTE_STAGE)
            execute_btn.clicked.connect(lambda _, s=step: self.execute_stage_requested.emit(s))

            sec.add_widget(execute_btn)
            self._execute_buttons[step] = execute_btn
            self._register_stage(step.value, sec)

    def _register_stage(self, stage_id: str, section: AccordionSection) -> None:
        """Register a stage section in lookup dictionary and add to layout."""
        self._stage_sections[stage_id] = section
        self.add_section(section)

    def notify_param_changed(self, step: str, param: str, value: Any) -> None:
        """Notify listeners that a stage parameter changed."""
        self.step_param_changed.emit(step, param, value)
