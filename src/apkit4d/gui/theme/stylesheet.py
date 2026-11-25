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

A stylesheet can draw an arrow only from an image: the arrow of the drop-down lists is a small SVG
file, written once for each color in the temporary folder of the system.
"""

import tempfile
from pathlib import Path

from PySide6.QtGui import QColor, QPalette

from apkit4d.gui.theme import tokens
from apkit4d.gui.theme.colors import mix, plain_button_colors

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
_ARROW_FOLDER: Path = Path(tempfile.gettempdir()) / "apkit4d"
# a chevron with the stroke of the icons of the playback bar, in their square of 20 units
_ARROW_SVG: str = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20 20">'
    '<path d="M6 8 L10 12 L14 8" fill="none" stroke="{color}" stroke-width="1.8" '
    'stroke-linecap="round" stroke-linejoin="round"/></svg>'
)

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
    return (
        _control(_FIELDS, palette, tokens.SPACING)
        + f"""
{_selectors(_FIELDS)} {{
    selection-background-color: {accent};
    selection-color: {accent_text};
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
    selection-background-color: {accent};
    selection-color: {accent_text};
}}
"""
    )


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
    text-align: center;
}}
QProgressBar::chunk {{
    background-color: {_css(palette.color(ColorRole.Highlight))};
    border-radius: {tokens.SMALL_RADIUS}px;
}}
QToolTip {{
    background-color: {_css(palette.color(ColorRole.ToolTipBase))};
    color: {_css(palette.color(ColorRole.ToolTipText))};
    border: {BORDER_WIDTH}px solid {_css(mix(window, ink, tokens.BORDER_MIX))};
    padding: {tokens.SPACING // 2}px {tokens.SPACING}px;
}}
"""


def build_stylesheet(palette: QPalette) -> str:
    """
    Build the stylesheet of the whole application for the palette of a theme.

    Args:
        palette: Palette of the theme, the one that `build_palette` returns.

    Returns:
        The stylesheet, to set on the application together with the same palette.
    """
    return "".join(part(palette) for part in (_buttons, _fields, _group_boxes, _feedback))
