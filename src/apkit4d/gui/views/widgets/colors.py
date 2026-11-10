"""
Helpers to derive colors from the palette, so that the widgets follow the theme.
"""

from PySide6.QtGui import QColor


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
