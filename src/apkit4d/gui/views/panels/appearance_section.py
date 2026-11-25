"""Appearance accordion section for the left panel."""

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)

from apkit4d.gui.constants import names, texts, view_style
from apkit4d.gui.theme.themes import DEFAULT_THEME, THEME_COLORS
from apkit4d.gui.views.widgets.accordion import AccordionSection
from apkit4d.gui.views.widgets.color_button import ColorButton
from apkit4d.gui.views.widgets.frame_slider import FrameSlider
from apkit4d.visualization.data_mapper import TrajectoryColorMode

__all__ = ["AppearanceSection"]


class AppearanceSection(AccordionSection):
    """Accordion section hosting the controls that change the 3D view's appearance."""

    theme_switch_requested = Signal()
    colormap_chosen = Signal(str)
    opacity_changed = Signal(float)
    background_chosen = Signal(str)
    outline_chosen = Signal(str)
    trajectory_tail_changed = Signal(int)
    trajectory_color_mode_changed = Signal(object)
    trajectory_colormap_changed = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(texts.SECTION_APPEARANCE, parent=parent)
        self.setObjectName(names.APPEARANCE_SECTION)

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(0, 0, 0, 0)
        form.setSpacing(10)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)

        theme_button = QPushButton(texts.BUTTON_THEME)
        theme_button.setObjectName(names.THEME_BUTTON)
        theme_button.clicked.connect(self.theme_switch_requested)
        form.addRow(theme_button)

        self._colormap_combo = QComboBox()
        self._colormap_combo.setObjectName(names.COLORMAP_COMBO)
        self._colormap_combo.addItems(list(view_style.COLORMAPS))
        self._colormap_combo.currentTextChanged.connect(self.colormap_chosen)

        self._opacity_slider = FrameSlider(preview=False)
        self._opacity_slider.setObjectName(names.OPACITY_SLIDER)
        self._opacity_slider.setRange(view_style.OPACITY_MIN_PERCENT, view_style.OPACITY_MAX_PERCENT)
        self._opacity_slider.setValue(view_style.OPACITY_DEFAULT_PERCENT)
        self._opacity_slider.valueChanged.connect(self._on_opacity_moved)

        self._opacity_value = QLabel(texts.OPACITY_VALUE.format(percent=view_style.OPACITY_DEFAULT_PERCENT))
        self._opacity_value.setObjectName(names.OPACITY_VALUE)
        self._opacity_value.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        widest = texts.OPACITY_VALUE.format(percent=view_style.OPACITY_MAX_PERCENT)
        self._opacity_value.setMinimumWidth(self._opacity_value.fontMetrics().horizontalAdvance(widest))

        opacity_row = QWidget()
        opacity_layout = QHBoxLayout(opacity_row)
        opacity_layout.setContentsMargins(0, 0, 0, 0)
        opacity_layout.addWidget(self._opacity_slider)
        opacity_layout.addWidget(self._opacity_value)

        self._background_button = ColorButton(texts.DIALOG_BACKGROUND)
        self._background_button.setObjectName(names.BACKGROUND_BUTTON)
        self._background_button.color_chosen.connect(self.background_chosen)

        self._outline_button = ColorButton(texts.DIALOG_OUTLINE)
        self._outline_button.setObjectName(names.OUTLINE_BUTTON)
        self._outline_button.color_chosen.connect(self.outline_chosen)

        self._add_field(form, texts.BOX_COLORMAP, self._colormap_combo, names.COLORMAP_BOX)
        self._add_field(form, texts.BOX_OPACITY, opacity_row, names.OPACITY_BOX)
        self._add_field(form, texts.BOX_BACKGROUND, self._background_button, names.BACKGROUND_BOX)
        self._add_field(form, texts.BOX_OUTLINE, self._outline_button, names.OUTLINE_BOX)

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

        self._add_field(
            form,
            texts.BOX_TRAJECTORY_COLOR_MODE,
            self._trajectory_color_mode_combo,
            names.TRAJECTORY_COLOR_MODE_BOX,
        )
        self._add_field(
            form,
            texts.BOX_TRAJECTORY_COLORMAP,
            self._trajectory_colormap_combo,
            names.TRAJECTORY_COLORMAP_BOX,
        )
        self._add_field(
            form,
            texts.BOX_TRAJECTORY_TAIL,
            self._trajectory_tail_spinbox,
            names.TRAJECTORY_TAIL_BOX,
        )

        self.add_widget(form_widget)
        self.apply_theme(THEME_COLORS[DEFAULT_THEME])

    @property
    def colormap(self) -> str:
        """Name of the selected colormap."""
        return self._colormap_combo.currentText()

    @property
    def volume_opacity(self) -> float:
        """Opacity as a factor: 1.0 is the default look."""
        return self._opacity_slider.value() / 100

    @property
    def trajectory_tail_length(self) -> int:
        """Maximum trailing frame steps, or -1 for full history."""
        return self._trajectory_tail_spinbox.value()

    @property
    def trajectory_color_mode(self) -> TrajectoryColorMode:
        """Active trajectory coloring mode."""
        return self._trajectory_color_mode_combo.currentData()

    @property
    def trajectory_colormap(self) -> str:
        """Active speed colormap name."""
        return self._trajectory_colormap_combo.currentText()

    def set_background_color(self, color: str) -> None:
        """Show a background color on the color button."""
        self._background_button.set_color(color)

    def set_outline_color(self, color: str) -> None:
        """Show an outline color on the color button."""
        self._outline_button.set_color(color)

    def _on_opacity_moved(self, percent: int) -> None:
        self._opacity_value.setText(texts.OPACITY_VALUE.format(percent=percent))
        self.opacity_changed.emit(percent / 100)

    def _on_trajectory_color_mode_changed(self, _index: int) -> None:
        mode = self.trajectory_color_mode
        self._trajectory_colormap_combo.setEnabled(mode == TrajectoryColorMode.SPEED)
        self.trajectory_color_mode_changed.emit(mode)

    @staticmethod
    def _add_field(form: QFormLayout, label_text: str, widget: QWidget, object_name: str) -> None:
        label = QLabel(label_text)
        label.setObjectName(object_name)
        form.addRow(label, widget)
