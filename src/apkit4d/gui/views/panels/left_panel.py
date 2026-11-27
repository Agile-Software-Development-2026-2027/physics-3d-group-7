"""
Left column of the main window.

It holds the general settings of the 3D view, grouped in collapsible sections. The panel holds no logic:
it announces what the user chooses with signals, and shows what it is told with its methods.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names
from apkit4d.gui.theme.themes import THEME_COLORS, Theme
from apkit4d.gui.views.display.vis_sub_roi_section import VisSubRoiSection
from apkit4d.gui.views.histograms.histograms_section import HistogramsSection
from apkit4d.gui.views.panels.appearance_section import AppearanceSection
from apkit4d.gui.views.panels.side_panel import SidePanel
from apkit4d.gui.views.widgets.scroll_area import ModernScrollArea
from apkit4d.gui.views.widgets.wheel_guard import install_wheel_guard


class LeftPanel(SidePanel):
    """
    Left column, with the appearance of the view and its layers in two collapsible sections.

    Signals:
        show_trajectories_toggled: Emitted when the trajectory visibility checkbox changes.
        show_blobs_toggled: Emitted when the blob visibility checkbox changes.
    """

    show_trajectories_toggled = Signal(bool)
    show_blobs_toggled = Signal(bool)

    def __init__(self) -> None:
        super().__init__(names.LEFT_PANEL)

        # the sections scroll, so the stretch of SidePanel is not needed
        while self._layout.count() > 0:
            self._layout.takeAt(0)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)

        self._scroll_area = ModernScrollArea(self)
        self._scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._appearance_section = AppearanceSection()
        self._vis_sub_roi_section = VisSubRoiSection()
        self._histograms_section = HistogramsSection()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)
        content_layout.addWidget(self._appearance_section)
        content_layout.addWidget(self._vis_sub_roi_section)
        content_layout.addWidget(self._histograms_section)
        content_layout.addStretch()  # keeps the sections at the top

        self._scroll_area.setWidget(content)
        self._layout.addWidget(self._scroll_area, stretch=1)

        # after adding the content, because the section measures it to open
        self._appearance_section.set_expanded(True, animate=False)
        self._wheel_guard = install_wheel_guard(self)

    @property
    def appearance_section(self) -> AppearanceSection:
        """Section with the settings of the look of the 3D view."""
        return self._appearance_section

    @property
    def vis_sub_roi_section(self) -> VisSubRoiSection:
        """Section with the Visualization Sub-ROI controls."""
        return self._vis_sub_roi_section

    @property
    def histograms_section(self) -> HistogramsSection:
        """Section with the intensity histograms."""
        return self._histograms_section

    def set_background_color(self, color: str) -> None:
        """
        Show `color` as the background color of the 3D view.

        Args:
            color: A color name or a hex code.
        """
        self._appearance_section.set_background_color(color)

    def set_outline_color(self, color: str) -> None:
        """
        Show `color` as the color of the outline of the volume.

        Args:
            color: A color name or a hex code.
        """
        self._appearance_section.set_outline_color(color)

    def set_theme(self, theme: Theme) -> None:
        """
        Paint the sections with `theme`, because the palette of the application does not reach them.

        Args:
            theme: Theme to apply.
        """
        colors = THEME_COLORS[theme]
        self._scroll_area.apply_theme(colors)
        self._appearance_section.apply_theme(colors)
        self._vis_sub_roi_section.apply_theme(colors)
        self._histograms_section.apply_theme(colors)
