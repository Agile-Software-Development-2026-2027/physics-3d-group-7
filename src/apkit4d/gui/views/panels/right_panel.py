"""
Right column of the main window.

Houses the accordion controls and analysis settings inside a scrollable panel.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QSizePolicy, QVBoxLayout, QWidget

from apkit4d.gui.constants import names
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.shared.components.scroll_area import ModernScrollArea
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS, Theme, ThemeColors
from apkit4d.gui.views.panels.side_panel import SidePanel


class RightPanel(SidePanel):
    """
    Right column of the main window.

    Houses collapsible accordion sections inside a full-height modern scroll area,
    automatically keeping its appearance synchronized with the application theme.
    """

    def __init__(self) -> None:
        super().__init__(names.RIGHT_PANEL)
        self._theme: Theme = DEFAULT_THEME
        self._sections: list[AccordionSection] = []
        # occupy all available space in the main window
        while self._layout.count() > 0:
            self._layout.takeAt(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.scroll_area = ModernScrollArea(self)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        # Content container inside scroll area
        self._scroll_content = QWidget()
        self._scroll_content.setObjectName("accordionScrollContent")
        self.accordion_layout = QVBoxLayout(self._scroll_content)
        self.accordion_layout.setContentsMargins(4, 4, 4, 4)
        self.accordion_layout.setSpacing(6)

        # Bottom stretch inside scroll content keeps collapsed sections pinned to the top
        self.accordion_layout.addStretch()

        self.scroll_area.setWidget(self._scroll_content)
        self._layout.addWidget(self.scroll_area, stretch=1)

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
        Apply theme to the right panel, scroll area, and all accordion sections.

        Args:
            theme: Theme to apply.
        """
        self._theme = theme
        self.apply_theme(THEME_COLORS[theme])

    def apply_theme(self, colors: ThemeColors) -> None:
        """
        Apply theme colors to the scroll area and all accordion sections.

        Args:
            colors: Colors of the active theme.
        """
        self.scroll_area.apply_theme(colors)
        for section in self._sections:
            section.apply_theme(colors)

    def _populate_default_sections(self) -> None:
        """Populate initial accordion sections."""
        for i in range(1, 10):
            section = AccordionSection(f"Section {i}")
            for j in range(1, 4):
                section.add_widget(QLabel(f"Item {j} in Section {i}"))
            self.add_section(section)
