"""
Stylesheet of the whole application, so that the standard Qt controls look like the playback bar.

The playback bar paints its own widgets. The rest of the interface uses the standard controls of Qt
(push buttons, drop-down lists, text fields, group boxes, ...), which this stylesheet dresses with
the same tokens and the same shades: rounded corners, height of the controls, border, hover and the
ring of the keyboard focus.

The shades are not written here: they come from the functions of `theme.colors`, applied to the
palette of the theme, so a control painted by Qt and a control painted by hand have the same colors.

What is left out, on purpose:
    - subclasses that paint themselves, such as the buttons of the playback bar: only the exact Qt
      classes are styled (`.QPushButton`, not `QPushButton`);
    - flat buttons, such as the ones in the headers of the sections, which have their own stylesheet;
    - number fields with arrows (`QSpinBox`, `QDoubleSpinBox`): they keep the look of Qt until they
      become `NumberStepper`, which has the - and + buttons of the playback bar.

The open list of a drop-down list is drawn below the field, as a list (`combobox-popup: 0`) and not
as a menu over the field: only in this way Qt draws its items with the stylesheet, as rounded rows
with the hover shade of the buttons.

A stylesheet can draw an arrow only from an image: the arrow of the drop-down lists is a small SVG
file, written once for each color in the temporary folder of the system.

The components of the application that have their own look (the sections of the side panels, the
bars of the right panel, the scroll bars) are styled here too, by their object names, so that every
color and size of the interface is in one place. A part that changes look with its state, such as the
header of a section that is running, gets that state as a property (`set_style_property`), which the
rules read as `[status="running"]`.
"""

import math
import tempfile
from pathlib import Path

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QWidget

from apkit4d.gui.constants import names
from apkit4d.gui.models.pipeline_model import StepStatus
from apkit4d.gui.theme import tokens
from apkit4d.gui.theme.colors import mix, plain_button_colors
from apkit4d.gui.theme.themes import STATUS_THEME_COLORS, THEME_COLORS, Theme

ColorRole = QPalette.ColorRole
ColorGroup = QPalette.ColorGroup

BORDER_WIDTH: int = 1
# the ring of the focus is thicker than the border: the padding shrinks by the difference, so that
# the content of the control does not move when it gets the focus
_RING_EXTRA: int = tokens.FOCUS_RING_WIDTH - BORDER_WIDTH
# min-height is the height of the content only: with padding and border the control is as high as
# the token
_CONTENT_HEIGHT: int = tokens.CONTROL_HEIGHT - 2 * tokens.FOCUS_RING_WIDTH
_ARROW_AREA: int = 24  # width of the area of the arrow of a drop-down list
# around the items of the open list: with the padding of the items, the texts of the list start where
# the text of the closed field starts
_LIST_PADDING: int = tokens.SPACING // 2
_ARROW_FOLDER: Path = Path(tempfile.gettempdir()) / "apkit4d"
# a chevron with the stroke of the icons of the playback bar, in their square of 20 units
_ARROW_SVG: str = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
    '<path d="M6 8 L10 12 L14 8" fill="none" stroke="{color}" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

# Qt cuts the moving bar of a busy progress bar square at the edges of the track, without following its
# round corners: inside a padding of 3/10 of the radius, the square ends stay within the round track
_PROGRESS_PADDING: int = math.ceil(0.3 * tokens.SMALL_RADIUS)
_SCROLL_BAR_WIDTH: int = tokens.SPACING
_MIN_SCROLL_HANDLE: int = 3 * tokens.SPACING  # shortest length of the handle of a scroll bar

_BUTTONS: tuple[str, ...] = ('.QPushButton[flat="false"]', "ColorButton")
_FIELDS: tuple[str, ...] = (".QComboBox", ".QLineEdit")


def _css(color: QColor) -> str:
    """The color as text for the stylesheet, with its transparency."""
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def _arrow_image(color: QColor) -> str:
    """
    Path of an image of a downward arrow of `color`, to use in the stylesheet.

    Args:
        color: Color of the arrow.

    Returns:
        The path, with forward slashes as the stylesheet wants on every operating system.
    """
    path = _ARROW_FOLDER / f"arrow_down_{color.name()[1:]}.svg"
    if not path.exists():
        _ARROW_FOLDER.mkdir(parents=True, exist_ok=True)
        path.write_text(_ARROW_SVG.format(color=color.name()), encoding="utf-8")
    return path.as_posix()


def _veil(color: QColor, amount: float) -> QColor:
    """
    `color` made transparent, so that over any background it gives `mix(background, color, amount)`.

    The headers of the sections change background with their status: a veil shades all of them in the
    same way, as the mixes of `theme.tokens` shade the controls.
    """
    veil = QColor(color)
    veil.setAlphaF(amount)
    return veil


def set_style_property(widget: QWidget, name: str, value: object) -> None:
    """
    Set a property that the stylesheet reads, such as the status of a section, and restyle the widget.

    Qt reads the properties only when it styles a widget, so the widget is styled again.

    Args:
        widget: Widget to restyle.
        name: Name of the property, as the stylesheet reads it (`[name="value"]`).
        value: New value of the property.
    """
    widget.setProperty(name, value)
    widget.style().unpolish(widget)
    widget.style().polish(widget)


def _selectors(widgets: tuple[str, ...], state: str = "") -> str:
    """`widgets` joined as one selector, each with the same pseudo-state, such as ":hover"."""
    return ", ".join(f"{widget}{state}" for widget in widgets)


def _control(widgets: tuple[str, ...], palette: QPalette, padding: int) -> str:
    """Shape, colors, focus ring and disabled look shared by the buttons and by the fields."""
    background, border, ink = plain_button_colors(palette, enabled=True, down=False, hovered=False)
    disabled_background, disabled_border, disabled_ink = plain_button_colors(
        palette, enabled=False, down=False, hovered=False
    )
    return f"""
{_selectors(widgets)} {{
    background-color: {_css(background)};
    color: {_css(ink)};
    border: {BORDER_WIDTH}px solid {_css(border)};
    border-radius: {tokens.BUTTON_RADIUS}px;
    padding: {_RING_EXTRA}px {padding}px;
    min-height: {_CONTENT_HEIGHT}px;
}}
{_selectors(widgets, ":focus")} {{
    border: {tokens.FOCUS_RING_WIDTH}px solid {_css(palette.color(ColorRole.Highlight))};
    padding: 0px {padding - _RING_EXTRA}px;
}}
{_selectors(widgets, ":disabled")} {{
    background-color: {_css(disabled_background)};
    color: {_css(disabled_ink)};
    border-color: {_css(disabled_border)};
}}
"""


def _buttons(palette: QPalette) -> str:
    """Push buttons with a text: like the buttons of the playback bar."""
    hovered, _, _ = plain_button_colors(palette, enabled=True, down=False, hovered=True)
    pressed, _, _ = plain_button_colors(palette, enabled=True, down=True, hovered=False)
    return (
        _control(_BUTTONS, palette, tokens.CONTROL_PADDING)
        + f"""
{_selectors(_BUTTONS, ":hover")} {{ background-color: {_css(hovered)}; }}
{_selectors(_BUTTONS, ":pressed")}, {_selectors(_BUTTONS, ":checked")} {{
    background-color: {_css(pressed)};
}}
"""
    )


def _fields(palette: QPalette) -> str:
    """Drop-down lists and text fields: like the speed field of the playback bar."""
    accent = _css(palette.color(ColorRole.Highlight))
    accent_text = _css(palette.color(ColorRole.HighlightedText))
    _, border, ink = plain_button_colors(palette, enabled=True, down=False, hovered=False)
    hovered, _, _ = plain_button_colors(palette, enabled=True, down=False, hovered=True)
    return (
        _control(_FIELDS, palette, tokens.SPACING)
        + f"""
{_selectors(_FIELDS)} {{
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
.QComboBox {{
    combobox-popup: 0;
}}
.QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    width: {_ARROW_AREA}px;
    border: none;
}}
.QComboBox::down-arrow {{
    image: url("{_arrow_image(ink)}");
    width: {tokens.SMALL_ICON_SIZE}px;
    height: {tokens.SMALL_ICON_SIZE}px;
}}
.QComboBox::down-arrow:disabled {{
    image: url("{_arrow_image(palette.color(ColorGroup.Disabled, ColorRole.ButtonText))}");
}}
.QComboBox QAbstractItemView {{
    background-color: {_css(palette.color(ColorRole.Base))};
    color: {_css(ink)};
    border: {BORDER_WIDTH}px solid {_css(border)};
    padding: {_LIST_PADDING}px;
    outline: 0px;
}}
.QComboBox QAbstractItemView::item {{
    min-height: {_CONTENT_HEIGHT}px;
    padding: 0px {tokens.SPACING - _LIST_PADDING}px;
    border-radius: {tokens.SMALL_RADIUS}px;
}}
.QComboBox QAbstractItemView::item:selected {{
    background-color: {_css(hovered)};
    color: {_css(ink)};
}}
"""
    )


def _drop_surface(palette: QPalette) -> str:
    """Dashed, rounded file drop area with a button-like hover state."""
    window = palette.color(ColorRole.Window)
    ink = palette.color(ColorRole.WindowText)
    border = mix(window, ink, tokens.BORDER_MIX)
    hovered, _, _ = plain_button_colors(palette, enabled=True, down=False, hovered=True)
    selector = f"QLabel#{names.CENTER_PLACEHOLDER}"
    drag_selector = f'{selector}[dragActive="true"]'
    return f"""
{selector} {{
    background-color: {_css(palette.color(ColorRole.Base))};
    color: {_css(palette.color(ColorRole.PlaceholderText))};
    border: 2px dashed {_css(border)};
    border-radius: {tokens.BUTTON_RADIUS}px;
    padding: {tokens.GROUP_SPACING * 2}px;
}}
{drag_selector} {{
    background-color: {_css(hovered)};
    color: {_css(ink)};
    border-color: {_css(palette.color(ColorRole.Highlight))};
}}
"""


def _group_boxes(palette: QPalette) -> str:
    """Frames around a group of controls, with a title: the border of a control, but larger."""
    window = palette.color(ColorRole.Window)
    ink = palette.color(ColorRole.WindowText)
    return f"""
QGroupBox {{
    border: {BORDER_WIDTH}px solid {_css(mix(window, ink, tokens.BORDER_MIX))};
    border-radius: {tokens.BUTTON_RADIUS}px;
    margin-top: {tokens.ROW_SPACING + tokens.SPACING}px;
    padding-top: {tokens.SPACING}px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: {tokens.SPACING}px;
    padding: 0px {tokens.SPACING // 2}px;
    color: {_css(mix(window, ink, tokens.MUTED_MIX))};
}}
"""


def _feedback(palette: QPalette) -> str:
    """Progress bars and tooltips."""
    window = palette.color(ColorRole.Window)
    ink = palette.color(ColorRole.WindowText)
    return f"""
QProgressBar {{
    background-color: {_css(mix(window, ink, tokens.GROOVE_MIX))};
    color: {_css(ink)};
    border: none;
    border-radius: {tokens.SMALL_RADIUS}px;
    padding: {_PROGRESS_PADDING}px;
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {_css(palette.color(ColorRole.Highlight))};
    border-radius: {tokens.SMALL_RADIUS - _PROGRESS_PADDING}px;
}}
QToolTip {{
    background-color: {_css(palette.color(ColorRole.ToolTipBase))};
    color: {_css(palette.color(ColorRole.ToolTipText))};
    border: {BORDER_WIDTH}px solid {_css(mix(window, ink, tokens.BORDER_MIX))};
    padding: {tokens.SPACING // 2}px {tokens.SPACING}px;
}}
"""


def _scroll_bars(palette: QPalette) -> str:
    """Slim scroll bars without arrows, whose handle takes the accent color under the mouse."""
    return f"""
QScrollArea#{names.MODERN_SCROLL_AREA} {{
    background-color: transparent;
    border: none;
}}
QScrollBar {{
    background: transparent;
    border: none;
    margin: 0px;
}}
QScrollBar:vertical {{ width: {_SCROLL_BAR_WIDTH}px; }}
QScrollBar:horizontal {{ height: {_SCROLL_BAR_WIDTH}px; }}
QScrollBar::handle {{
    background-color: {_css(palette.color(ColorRole.PlaceholderText))};
    border-radius: {_SCROLL_BAR_WIDTH // 2}px;
}}
QScrollBar::handle:vertical {{ min-height: {_MIN_SCROLL_HANDLE}px; }}
QScrollBar::handle:horizontal {{ min-width: {_MIN_SCROLL_HANDLE}px; }}
QScrollBar::handle:hover {{ background-color: {_css(palette.color(ColorRole.Highlight))}; }}
QScrollBar::handle:pressed {{ background-color: {_css(palette.color(ColorRole.Link))}; }}
QScrollBar::add-line, QScrollBar::sub-line {{
    background: none;
    border: none;
    width: 0px;
    height: 0px;
}}
QScrollBar::add-page, QScrollBar::sub-page {{ background: none; }}
"""


def _sections(palette: QPalette, theme: Theme) -> str:
    """
    Collapsible sections of the side panels: a header as high as a control, then the content.

    The header takes the background of the status of its step (`[status="running"]`, ...), and loses
    its lower corners while the section is open (`[expanded="true"]`), to join the content.
    """
    window = palette.color(ColorRole.Window)
    ink = palette.color(ColorRole.WindowText)
    border = _css(mix(window, ink, tokens.BORDER_MIX))
    header = f"QFrame#{names.ACCORDION_HEADER_FRAME}"
    toggle = f"QPushButton#{names.ACCORDION_TOGGLE_BUTTON}"
    # small buttons inside a header, such as the play button of a step
    actions = (f"QPushButton#{names.PLAY_STAGE_BUTTON}", f"QPushButton#{names.BOTTOM_STATS_TOGGLE_BUTTON}")
    content = f"QFrame#{names.ACCORDION_CONTENT_AREA}"
    inner_radius = tokens.BUTTON_RADIUS - BORDER_WIDTH  # the toggle button sits inside the border
    rules = f"""
{header} {{
    background-color: {_css(palette.color(ColorRole.Button))};
    border: {BORDER_WIDTH}px solid {border};
    border-radius: {tokens.BUTTON_RADIUS}px;
}}
{header}[expanded="true"] {{
    border-bottom-left-radius: 0px;
    border-bottom-right-radius: 0px;
}}
{toggle} {{
    background-color: transparent;
    color: {_css(palette.color(ColorRole.ButtonText))};
    border: none;
    border-top-left-radius: {inner_radius}px;
    border-bottom-left-radius: {inner_radius}px;
    padding: 0px {tokens.SPACING}px;
    min-height: {tokens.CONTROL_HEIGHT - 2 * BORDER_WIDTH}px;
    text-align: left;
    font-weight: bold;
}}
{toggle}:hover {{ background-color: {_css(_veil(ink, tokens.HOVER_MIX))}; }}
{toggle}:checked {{ border-bottom-left-radius: 0px; }}
{_selectors(actions)} {{
    background-color: transparent;
    color: {_css(palette.color(ColorRole.ButtonText))};
    border: {BORDER_WIDTH}px solid transparent;
    border-radius: {tokens.SMALL_RADIUS}px;
    padding: 0px;
    font-weight: bold;
}}
{_selectors(actions, ":hover")} {{
    background-color: {_css(_veil(ink, tokens.HOVER_MIX))};
    border-color: {_css(_veil(ink, tokens.BORDER_MIX))};
}}
{_selectors(actions, ":pressed")} {{
    background-color: {_css(_veil(ink, tokens.BORDER_MIX))};
}}
{content} {{
    background-color: {THEME_COLORS[theme].raised_base};
    border: {BORDER_WIDTH}px solid {border};
    border-top: none;
    border-bottom-left-radius: {tokens.BUTTON_RADIUS}px;
    border-bottom-right-radius: {tokens.BUTTON_RADIUS}px;
}}
{content} QLabel {{
    background-color: transparent;
    color: {_css(palette.color(ColorRole.Text))};
    border: none;
}}
"""
    statuses = STATUS_THEME_COLORS[theme]
    for status, background, text in (
        (StepStatus.PENDING, statuses.pending_bg, statuses.pending_text),
        (StepStatus.RUNNING, statuses.running_bg, statuses.running_text),
        (StepStatus.COMPLETED, statuses.completed_bg, statuses.completed_text),
    ):
        state = f'[status="{status.value}"]'
        rules += f"""
{header}{state} {{ background-color: {background}; }}
{toggle}{state}, QPushButton#{names.PLAY_STAGE_BUTTON}{state} {{ color: {text}; }}
"""
    return rules


def _right_panel(palette: QPalette) -> str:
    """The bar above the sections of the right panel and the statistics below them."""
    window = palette.color(ColorRole.Window)
    ink = palette.color(ColorRole.WindowText)
    border = _css(mix(window, ink, tokens.BORDER_MIX))
    return f"""
QFrame#{names.RIGHT_PANEL_TOP_BAR} {{
    background-color: {_css(window)};
    border-bottom: {BORDER_WIDTH}px solid {border};
}}
QFrame#{names.BOTTOM_STATS_SECTION} {{
    background-color: {_css(window)};
    border-top: {BORDER_WIDTH}px solid {border};
}}
QFrame#{names.BOTTOM_STATS_HEADER} {{
    background-color: transparent;
    border: none;
}}
QLabel#{names.BOTTOM_STATS_SUMMARY_LABEL} {{
    color: {_css(ink)};
    font-weight: bold;
}}
QFrame#{names.BOTTOM_STATS_DETAILS_FRAME} {{
    background-color: {_css(palette.color(ColorRole.Base))};
    border-top: {BORDER_WIDTH}px solid {border};
}}
QLabel#{names.BOTTOM_STATS_DETAILS_LABEL} {{
    color: {_css(palette.color(ColorRole.Text))};
}}
"""


def build_stylesheet(palette: QPalette, theme: Theme) -> str:
    """
    Build the stylesheet of the whole application for a theme.

    Args:
        palette: Palette of the theme, the one that `build_palette` returns.
        theme: The theme, for the colors that are not in the palette (status of the sections, ...).

    Returns:
        The stylesheet, to set on the application together with the same palette.
    """
    parts = (
        _buttons(palette),
        _fields(palette),
        _drop_surface(palette),
        _group_boxes(palette),
        _feedback(palette),
    )
    return "".join(parts) + _scroll_bars(palette) + _sections(palette, theme) + _right_panel(palette)
