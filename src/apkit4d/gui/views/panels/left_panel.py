"""
Left column of the main window.

It holds the general settings of the 3D view, grouped in collapsible sections. The panel holds no logic:
it announces what the user chooses with signals, and shows what it is told with its methods.
"""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from apkit4d.gui.constants import names, texts, view_style
from apkit4d.gui.theme.themes import THEME_COLORS, Theme
from apkit4d.gui.views.histograms.histograms_section import HistogramsSection
from apkit4d.gui.views.panels.side_panel import SidePanel
from apkit4d.gui.views.widgets.accordion import AccordionSection
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.gui.views.widgets.scroll_area import ModernScrollArea
from apkit4d.visualization.data_mapper import TrajectoryColorMode


class LeftPanel(SidePanel):
    """
    Left column, with the appearance of the view and its layers in two collapsible sections.

    Signals:
        theme_switch_requested: The user pressed the theme button.
        colormap_chosen: Emitted with the name of the colormap the user chose.
        opacity_changed: Emitted with the opacity the user chose, as a factor: 1.0 is the default look.
        background_chosen: Emitted with the hex code of the background color the user chose.
        outline_chosen: Emitted with the hex code of the outline color the user chose.
        show_trajectories_toggled: Emitted when the trajectory visibility checkbox changes.
        show_blobs_toggled: Emitted when the blob visibility checkbox changes.
        trajectory_tail_changed: Emitted with the trajectory tail length (`-1` for all steps).
        trajectory_color_mode_changed: Emitted with the selected `TrajectoryColorMode`.
        trajectory_colormap_changed: Emitted with the selected speed colormap name.
    """

    theme_switch_requested = Signal()
    colormap_chosen = Signal(str)
    opacity_changed = Signal(float)
    background_chosen = Signal(str)
    outline_chosen = Signal(str)
    show_trajectories_toggled = Signal(bool)
    show_blobs_toggled = Signal(bool)
    trajectory_tail_changed = Signal(int)
    trajectory_color_mode_changed = Signal(object)
    trajectory_colormap_changed = Signal(str)

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

        # the signals are connected after the starting values, so that setting them emits nothing
        self._colormap_combo = QComboBox()
        self._colormap_combo.setObjectName(names.COLORMAP_COMBO)
        self._colormap_combo.addItems(list(view_style.COLORMAPS))
        self._colormap_combo.currentTextChanged.connect(self.colormap_chosen)

        self._opacity_slider = FrameSlider(preview=False)  # its bubble would show frame numbers
        self._opacity_slider.setObjectName(names.OPACITY_SLIDER)
        self._opacity_slider.setRange(view_style.OPACITY_MIN_PERCENT, view_style.OPACITY_MAX_PERCENT)
        self._opacity_slider.setValue(view_style.OPACITY_DEFAULT_PERCENT)
        self._opacity_slider.valueChanged.connect(self._on_opacity_moved)

        self._opacity_value = QLabel(texts.OPACITY_VALUE.format(percent=view_style.OPACITY_DEFAULT_PERCENT))
        self._opacity_value.setObjectName(names.OPACITY_VALUE)
        self._opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        # as wide as the widest value, so that the slider does not change size while it moves
        widest = texts.OPACITY_VALUE.format(percent=view_style.OPACITY_MAX_PERCENT)
        self._opacity_value.setMinimumWidth(self._opacity_value.fontMetrics().horizontalAdvance(widest))

        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.addWidget(self._opacity_slider, stretch=1)
        opacity_layout.addWidget(self._opacity_value)

        self._background_button = ColorButton(texts.DIALOG_BACKGROUND)
        self._background_button.setObjectName(names.BACKGROUND_BUTTON)
        self._background_button.color_chosen.connect(self.background_chosen)

        self._outline_button = ColorButton(texts.DIALOG_OUTLINE)
        self._outline_button.setObjectName(names.OUTLINE_BUTTON)
        self._outline_button.color_chosen.connect(self.outline_chosen)

        self._appearance_section = AccordionSection(texts.SECTION_APPEARANCE)
        self._appearance_section.setObjectName(names.APPEARANCE_SECTION)
        self._appearance_section.add_widget(theme_button)
        self._colormap_box = self._add_box(
            self._appearance_section, texts.BOX_COLORMAP, names.COLORMAP_BOX, self._colormap_combo
        )
        self._opacity_box = self._add_box(
            self._appearance_section, texts.BOX_OPACITY, names.OPACITY_BOX, opacity_row
        )
        self._background_box = self._add_box(
            self._appearance_section, texts.BOX_BACKGROUND, names.BACKGROUND_BOX, self._background_button
        )
        self._outline_box = self._add_box(
            self._appearance_section, texts.BOX_OUTLINE, names.OUTLINE_BOX, self._outline_button
        )

        self._show_trajectories_checkbox = QCheckBox(texts.LABEL_SHOW_TRAJECTORIES)
        self._show_trajectories_checkbox.setObjectName(names.SHOW_TRAJECTORIES_CHECKBOX)
        self._show_trajectories_checkbox.setChecked(True)
        self._show_trajectories_checkbox.toggled.connect(self.show_trajectories_toggled)
        self._show_trajectories_checkbox.hide()

        self._show_blobs_checkbox = QCheckBox(texts.LABEL_SHOW_BLOBS)
        self._show_blobs_checkbox.setObjectName(names.SHOW_BLOBS_CHECKBOX)
        self._show_blobs_checkbox.setChecked(True)
        self._show_blobs_checkbox.toggled.connect(self.show_blobs_toggled)
        self._show_blobs_checkbox.hide()

        self._trajectory_tail_spinbox = QSpinBox()
        self._trajectory_tail_spinbox.setObjectName(names.TRAJECTORY_TAIL_SPINBOX)
        self._trajectory_tail_spinbox.setRange(view_style.TRAJECTORY_TAIL_MIN, view_style.TRAJECTORY_TAIL_MAX)
        self._trajectory_tail_spinbox.setSpecialValueText(texts.TRAJECTORY_TAIL_ALL)
        self._trajectory_tail_spinbox.setValue(view_style.TRAJECTORY_TAIL_DEFAULT)
        self._trajectory_tail_spinbox.valueChanged.connect(self.trajectory_tail_changed)

        self._trajectory_color_mode_combo = QComboBox()
        self._trajectory_color_mode_combo.setObjectName(names.TRAJECTORY_COLOR_MODE_COMBO)
        self._trajectory_color_mode_combo.addItem(texts.TRAJECTORY_COLOR_SPEED, TrajectoryColorMode.SPEED)
        self._trajectory_color_mode_combo.addItem(
            texts.TRAJECTORY_COLOR_TRACK_ID, TrajectoryColorMode.TRACK_ID
        )
        self._trajectory_color_mode_combo.currentIndexChanged.connect(self._on_trajectory_color_mode_changed)

        self._trajectory_colormap_combo = QComboBox()
        self._trajectory_colormap_combo.setObjectName(names.TRAJECTORY_COLORMAP_COMBO)
        self._trajectory_colormap_combo.addItems(list(view_style.TRAJECTORY_COLORMAPS))
        self._trajectory_colormap_combo.currentTextChanged.connect(self.trajectory_colormap_changed)

        self._trajectory_color_mode_box = self._add_box(
            self._appearance_section,
            texts.BOX_TRAJECTORY_COLOR_MODE,
            names.TRAJECTORY_COLOR_MODE_BOX,
            self._trajectory_color_mode_combo,
        )
        self._trajectory_colormap_box = self._add_box(
            self._appearance_section,
            texts.BOX_TRAJECTORY_COLORMAP,
            names.TRAJECTORY_COLORMAP_BOX,
            self._trajectory_colormap_combo,
        )

        self._layers_section = AccordionSection(texts.SECTION_LAYERS)
        self._layers_section.setObjectName(names.LAYERS_SECTION)
        self._layers_section.add_widget(self._show_trajectories_checkbox)
        self._layers_section.add_widget(self._show_blobs_checkbox)
        self._trajectory_tail_box = self._add_box(
            self._layers_section,
            texts.BOX_TRAJECTORY_TAIL,
            names.TRAJECTORY_TAIL_BOX,
            self._trajectory_tail_spinbox,
        )

        self._histograms_section = HistogramsSection()

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(4, 4, 4, 4)
        content_layout.setSpacing(6)
        content_layout.addWidget(self._appearance_section)
        content_layout.addWidget(self._layers_section)
        content_layout.addWidget(self._histograms_section)
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
    def histograms_section(self) -> HistogramsSection:
        """Section with the intensity histograms."""
        return self._histograms_section

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

    @property
    def colormap(self) -> str:
        """Name of the colormap chosen in the panel."""
        return self._colormap_combo.currentText()

    @property
    def volume_opacity(self) -> float:
        """Opacity chosen in the panel, as a factor: 1.0 is the default look."""
        return self._opacity_slider.value() / 100

    @property
    def show_trajectories(self) -> bool:
        """Whether 3D trajectory paths are enabled."""
        return self._show_trajectories_checkbox.isChecked()

    @property
    def show_blobs(self) -> bool:
        """Whether 3D blob markers are enabled."""
        return self._show_blobs_checkbox.isChecked()

    @property
    def trajectory_tail_length(self) -> int:
        """Maximum number of trailing frame steps shown, or `-1` for full history."""
        return self._trajectory_tail_spinbox.value()

    @property
    def trajectory_color_mode(self) -> TrajectoryColorMode:
        """Active trajectory coloring mode."""
        return self._trajectory_color_mode_combo.currentData()

    @property
    def trajectory_colormap(self) -> str:
        """Active matplotlib colormap name when coloring trajectories by speed."""
        return self._trajectory_colormap_combo.currentText()

    def set_background_color(self, color: str) -> None:
        """
        Show `color` as the background color of the 3D view.

        Args:
            color: A color name or a hex code.
        """
        self._background_button.set_color(color)

    def set_outline_color(self, color: str) -> None:
        """
        Show `color` as the color of the outline of the volume.

        Args:
            color: A color name or a hex code.
        """
        self._outline_button.set_color(color)

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
        self._histograms_section.apply_theme(colors)

    def _on_opacity_moved(self, percent: int) -> None:
        self._opacity_value.setText(texts.OPACITY_VALUE.format(percent=percent))
        self.opacity_changed.emit(percent / 100)

    def _on_trajectory_color_mode_changed(self, _index: int) -> None:
        mode = self.trajectory_color_mode
        self._trajectory_colormap_combo.setEnabled(mode == TrajectoryColorMode.SPEED)
        self.trajectory_color_mode_changed.emit(mode)

    def _add_box(self, section: AccordionSection, title: str, name: str, control: QWidget) -> QWidget:
        box = QWidget()
        box.setObjectName(name)
        layout = QVBoxLayout(box)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(title))
        layout.addWidget(control)
        section.add_widget(box)
        return box
