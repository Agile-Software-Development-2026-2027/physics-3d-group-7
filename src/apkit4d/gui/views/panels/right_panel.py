"""
Right column of the main window.

Houses the top control bar (e.g. toggle all), the scrollable accordion sections,
and a collapsible statistics and diagnostics section docked at the bottom.
"""

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.shared.components.scroll_area import ModernScrollArea
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, Theme, ThemeColors
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
        self.setObjectName("bottomStatsSection")
        self._is_expanded: bool = False

        self._main_layout = QVBoxLayout(self)
        self._main_layout.setContentsMargins(0, 0, 0, 0)
        self._main_layout.setSpacing(0)

        # Summary header (always visible)
        self._header = QFrame(self)
        self._header.setObjectName("bottomStatsHeader")
        header_layout = QHBoxLayout(self._header)
        header_layout.setContentsMargins(8, 6, 8, 6)
        header_layout.setSpacing(6)

        self._summary_label = QLabel("Working: 15%")
        self._summary_label.setObjectName("bottomStatsSummaryLabel")

        self._toggle_btn = QPushButton("▲")
        self._toggle_btn.setObjectName("bottomStatsToggleBtn")
        self._toggle_btn.setFixedSize(24, 20)
        self._toggle_btn.setToolTip("Toggle statistics details")
        self._toggle_btn.clicked.connect(lambda: self.toggle(animate=True))

        header_layout.addWidget(self._summary_label, stretch=1)
        header_layout.addWidget(self._toggle_btn)

        # Details container (collapsible)
        self._details_frame = QFrame(self)
        self._details_frame.setObjectName("bottomStatsDetailsFrame")
        self._details_layout = QVBoxLayout(self._details_frame)
        self._details_layout.setContentsMargins(8, 6, 8, 6)
        self._details_layout.setSpacing(4)

        self._details_label = QLabel(
            "Task: Processing Volume Data\nProgress: 15%\nElapsed: 00:01:24\nStatus: Active"
        )
        self._details_label.setObjectName("bottomStatsDetailsLabel")
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
        # TODO: we migth want to switch this to a custom Widget to have more control over it
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
        self._toggle_btn.setText("▼" if expanded else "▲")

        target_height = self._details_layout.sizeHint().height() + 12 if expanded else 0

        if animate:
            self._animation.stop()
            self._animation.setStartValue(self._details_frame.height())
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
        self.setStyleSheet(f"""
            QFrame#apply_themebottomStatsSection {{
                background-color: {colors.window};
                border-top: 1px solid {colors.alternate_base};
            }}
            QFrame#bottomStatsHeader {{
                background-color: transparent;
                border: none;
            }}
            QLabel#bottomStatsSummaryLabel {{
                color: {colors.window_text};
                font-weight: bold;
                font-size: 12px;
                background-color: transparent;
                border: none;
            }}
            QPushButton#bottomStatsToggleBtn {{
                background-color: {colors.button};
                color: {colors.button_text};
                border: 1px solid {colors.alternate_base};
                border-radius: 3px;
                font-size: 10px;
                padding: 0px;
            }}
            QPushButton#bottomStatsToggleBtn:hover {{
                background-color: {colors.alternate_base};
            }}
            QFrame#bottomStatsDetailsFrame {{
                background-color: {colors.base};
                border-top: 1px solid {colors.alternate_base};
            }}
            QLabel#bottomStatsDetailsLabel {{
                color: {colors.text};
                font-size: 11px;
                background-color: transparent;
                border: none;
            }}
        """)


class RightPanel(SidePanel):
    """
    Right column of the main window.

    Houses:
    - Top bar: action controls such as 'Toggle All'.
    - Middle: collapsible accordion sections inside a full-height modern scroll area.
    - Bottom: collapsible statistics panel supporting summary and detailed states.
    """

    def __init__(self) -> None:
        super().__init__(names.RIGHT_PANEL)
        self._theme: Theme = DEFAULT_THEME
        self._sections: list[AccordionSection] = []

        # Occupy all available space in the main window
        while self._layout.count() > 0:
            self._layout.takeAt(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.top_bar = QFrame(self)
        self.top_bar.setObjectName("rightPanelTopBar")
        top_layout = QHBoxLayout(self.top_bar)
        top_layout.setContentsMargins(6, 6, 6, 6)
        top_layout.setSpacing(6)

        # Top Area (Controls)
        self.toggle_all_btn = QPushButton("Toggle All", self.top_bar)
        self.toggle_all_btn.setObjectName("toggleAllButton")
        self.toggle_all_btn.setToolTip("Toggle collapse/expand state of all accordion sections")
        self.toggle_all_btn.clicked.connect(self.toggle_all)
        top_layout.addWidget(self.toggle_all_btn)

        # Middle Area
        self.scroll_area = ModernScrollArea(self)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._scroll_content = QWidget()
        self._scroll_content.setObjectName("accordionScrollContent")
        self.accordion_layout = QVBoxLayout(self._scroll_content)
        self.accordion_layout.setContentsMargins(4, 4, 4, 4)
        self.accordion_layout.setSpacing(6)

        # Bottom stretch inside scroll content keeps collapsed sections pinned to the top
        self.accordion_layout.addStretch()
        self.scroll_area.setWidget(self._scroll_content)

        # Bottom Area (Info)
        self._bottom_stats = BottomStatsSection(self)

        # Assemble
        self._layout.addWidget(self.top_bar)
        self._layout.addWidget(self.scroll_area, stretch=1)
        self._layout.addWidget(self._bottom_stats)

        self._populate_default_sections()
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

    def toggle_all(self) -> None:
        """
        Toggle all accordion sections.

        If all sections are currently expanded, collapses them; otherwise expands all sections.
        """
        all_expanded = bool(self._sections) and all(s.is_expanded() for s in self._sections)
        self.set_all_expanded(not all_expanded)

    def expand_all(self) -> None:
        """Expand all accordion sections."""
        self.set_all_expanded(True)

    def collapse_all(self) -> None:
        """Collapse all accordion sections."""
        self.set_all_expanded(False)

    def set_all_expanded(self, expanded: bool, animate: bool = True) -> None:
        """
        Set expanded state on all accordion sections.

        Args:
            expanded: True to expand all, False to collapse all.
            animate: Whether to animate the transition.
        """
        for section in self._sections:
            section.set_expanded(expanded, animate=animate)

    def set_stats_summary(self, text: str) -> None:
        """
        Update the summary text of the bottom statistics section.

        Args:
            text: Summary text to show.
        """
        self._bottom_stats.set_summary(text)

    def set_stats_details(self, text: str) -> None:
        """
        Update the detailed statistics text of the bottom section.

        Args:
            text: Detailed statistics text to show.
        """
        self._bottom_stats.set_details(text)

    def toggle_stats(self, animate: bool = True) -> None:
        """
        Toggle between collapsed and expanded states of the bottom statistics section.

        Args:
            animate: Whether to animate the transition.
        """
        self._bottom_stats.toggle(animate=animate)

    def add_section(self, section: AccordionSection) -> None:
        """
        Add an accordion section above the bottom stretch.

        Args:
            section: Section to add.
        """
        self._sections.append(section)
        stretch_index = max(self.accordion_layout.count() - 1, 0)
        self.accordion_layout.insertWidget(stretch_index, section)
        section.apply_theme(THEME_COLORS[self._theme])

    def remove_section(self, section: AccordionSection) -> None:
        """
        Remove an accordion section from the panel.

        Args:
            section: Section to remove.
        """
        if section in self._sections:
            self._sections.remove(section)
            self.accordion_layout.removeWidget(section)
            section.setParent(None)
            section.deleteLater()

    def clear_sections(self) -> None:
        """Remove all accordion sections from the panel."""
        for section in list(self._sections):
            self.remove_section(section)

    def add_control(self, widget: QWidget) -> None:
        """
        Add a generic control widget inside the scrollable layout.

        Args:
            widget: Widget to add.
        """
        stretch_index = max(self.accordion_layout.count() - 1, 0)
        self.accordion_layout.insertWidget(stretch_index, widget)

    def set_theme(self, theme: Theme) -> None:
        """
        Apply theme to the right panel, top bar, scroll area, sections, and stats.

        Args:
            theme: Theme to apply.
        """
        self._theme = theme
        self.apply_theme(THEME_COLORS[theme])

    def apply_theme(self, colors: ThemeColors) -> None:
        """
        Apply theme colors to all components.

        Args:
            colors: Colors of the active theme.
        """
        self._style_top_bar(colors)
        self.scroll_area.apply_theme(colors)
        for section in self._sections:
            section.apply_theme(colors)
        self._bottom_stats.apply_theme(colors)

    def _style_top_bar(self, colors: ThemeColors) -> None:
        """Style the top control bar with the active theme colors."""
        self.top_bar.setStyleSheet(f"""
            QFrame#rightPanelTopBar {{
                background-color: {colors.window};
                border-bottom: 1px solid {colors.alternate_base};
            }}
            QPushButton#toggleAllButton {{
                background-color: {colors.button};
                color: {colors.button_text};
                border: 1px solid {colors.alternate_base};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
                font-weight: bold;
            }}
            QPushButton#toggleAllButton:hover {{
                background-color: {colors.alternate_base};
            }}
            QPushButton#toggleAllButton:pressed {{
                background-color: {colors.highlight};
                color: {colors.highlighted_text};
            }}
        """)

    def _populate_default_sections(self) -> None:
        """Populate initial accordion sections."""
        for i in range(1, 10):
            section = AccordionSection(f"Section {i}")
            for j in range(1, 4):
                section.add_widget(QLabel(f"Item {j} in Section {i}"))
            self.add_section(section)
