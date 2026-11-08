"""
Left column of the main window.

It holds the general settings of the 3D view, grouped in collapsible sections.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QPushButton, QVBoxLayout, QWidget

from apkit4d.gui.constants import names, texts
from apkit4d.gui.shared.components.accordion import AccordionSection
from apkit4d.gui.shared.components.scroll_area import ModernScrollArea
from apkit4d.gui.theme.themes import THEME_COLORS, Theme
from apkit4d.gui.views.panels.side_panel import SidePanel


class LeftPanel(SidePanel):
    """
    Left column, with the appearance of the view and its layers in two collapsible sections.

    Signals:
        theme_switch_requested: The user pressed the theme button.
    """

    theme_switch_requested = Signal()

    def __init__(self) -> None:
        super().__init__(names.LEFT_PANEL)

        # the sections scroll, so the stretch of SidePanel is not needed
        while self._layout.count() > 0:
            self._layout.takeAt(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._scroll_area = ModernScrollArea(self)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        theme_button = QPushButton(texts.BUTTON_THEME)
        theme_button.setObjectName(names.THEME_BUTTON)
        theme_button.clicked.connect(self.theme_switch_requested)

        self._appearance_section = AccordionSection(texts.SECTION_APPEARANCE)
        self._appearance_section.setObjectName(names.APPEARANCE_SECTION)
        self._appearance_section.add_widget(theme_button)
        self._colormap_box = self._add_box(texts.BOX_COLORMAP, names.COLORMAP_BOX)
        self._opacity_box = self._add_box(texts.BOX_OPACITY, names.OPACITY_BOX)
        self._background_box = self._add_box(texts.BOX_BACKGROUND, names.BACKGROUND_BOX)
        self._outline_box = self._add_box(texts.BOX_OUTLINE, names.OUTLINE_BOX)

        self._layers_section = AccordionSection(texts.SECTION_LAYERS)
        self._layers_section.setObjectName(names.LAYERS_SECTION)
        self._layers_section.add_widget(QLabel(texts.LAYERS_EMPTY))

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)
        content_layout.addWidget(self._appearance_section)
        content_layout.addWidget(self._layers_section)
        content_layout.addStretch()  # keeps the sections at the top

        self._scroll_area.setWidget(content)
        self._layout.addWidget(self._scroll_area, stretch=1)

        # after adding the content, because the section measures it to open
        self._appearance_section.set_expanded(True, animate=False)

    @property
    def appearance_section(self) -> AccordionSection:
        """Section with the settings of the look of the 3D view."""
        return self._appearance_section

    @property
    def layers_section(self) -> AccordionSection:
        """Section with the layers of the 3D view."""
        return self._layers_section

    @property
    def colormap_box(self) -> QWidget:
        """Box for the choice of the colormap of the volume."""
        return self._colormap_box

    @property
    def opacity_box(self) -> QWidget:
        """Box for the opacity of the volume."""
        return self._opacity_box

    @property
    def background_box(self) -> QWidget:
        """Box for the background color of the 3D view."""
        return self._background_box

    @property
    def outline_box(self) -> QWidget:
        """Box for the color of the outline of the volume."""
        return self._outline_box

    def set_theme(self, theme: Theme) -> None:
        """
        Paint the sections with `theme`, because the palette of the application does not reach them.

        Args:
            theme: Theme to apply.
        """
        colors = THEME_COLORS[theme]
        self._scroll_area.apply_theme(colors)
        self._appearance_section.apply_theme(colors)
        self._layers_section.apply_theme(colors)

    def _add_box(self, title: str, name: str) -> QWidget:
        box = QWidget()
        box.setObjectName(name)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        self._appearance_section.add_widget(box)
        return box
