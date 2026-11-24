"""
Shades derived from the palette of the active theme, so that the components follow the theme.

The themes define a few base colors (window, text, button, accent, ...). Every other shade, such as
the border of a control or its background while the mouse is over it, is a mix of those colors with
the proportions in `theme.tokens`. Painting a component with these functions keeps it consistent
with the playback bar in every theme.
"""

from PySide6.QtGui import QColor, QPalette, QPen

from apkit4d.gui.theme import tokens

ColorRole = QPalette.ColorRole
ColorGroup = QPalette.ColorGroup

TRANSPARENT: QColor = QColor(0, 0, 0, 0)


def mix(first: QColor, second: QColor, amount: float) -> QColor:
    """
    Return a color between two colors.

    Args:
        first: The color returned when `amount` is 0.
        second: The color returned when `amount` is 1.
        amount: How far to go from `first` to `second`, from 0 to 1.
    """
    return QColor(
        round(first.red() + (second.red() - first.red()) * amount),
        round(first.green() + (second.green() - first.green()) * amount),
        round(first.blue() + (second.blue() - first.blue()) * amount),
    )


def plain_button_colors(
    palette: QPalette, *, enabled: bool, down: bool, hovered: bool, flat: bool = False
) -> tuple[QColor, QColor, QColor]:
    """
    Background, border and ink colors of a button that is not the one of the main action.

    Args:
        palette: Palette of the button.
        enabled: False if the button is disabled.
        down: True while the button is pressed.
        hovered: True while the mouse is over the button.
        flat: True for a button that has no background and no border until the mouse is over it.
    """
    window = palette.color(ColorRole.Window)
    ink = palette.color(ColorRole.WindowText)
    button = palette.color(ColorRole.Button)
    if not enabled:
        border = TRANSPARENT if flat else mix(window, ink, tokens.DISABLED_BORDER_MIX)
        return TRANSPARENT, border, palette.color(ColorGroup.Disabled, ColorRole.ButtonText)
    border = mix(window, ink, tokens.BORDER_MIX)
    background = TRANSPARENT if flat else button
    if down:
        background = border
    elif hovered:
        background = mix(button, ink, tokens.HOVER_MIX)
    return background, TRANSPARENT if flat else border, ink


def focus_pen(palette: QPalette, *, primary: bool = False) -> QPen:
    """
    Pen that draws the ring around the widget that has the keyboard focus.

    Args:
        palette: Palette of the widget.
        primary: True for the button of the main action, whose ring is lighter to stand out.
    """
    accent = palette.color(ColorRole.Highlight)
    color = mix(accent, QColor("white"), tokens.FOCUS_RING_LIGHTEN) if primary else accent
    return QPen(color, tokens.FOCUS_RING_WIDTH)
