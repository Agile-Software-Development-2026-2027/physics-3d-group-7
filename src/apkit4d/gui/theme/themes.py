"""
The themes of the application and their colors.
"""

from dataclasses import dataclass
from enum import Enum


class Theme(Enum):
    """The looks the application can have."""

    LIGHT = "light"
    DARK = "dark"

    @property
    def opposite(self) -> Theme:
        """The other theme, the one the switch button goes to."""
        return Theme.DARK if self is Theme.LIGHT else Theme.LIGHT


@dataclass(frozen=True)
class ThemeColors:
    """Colors of a theme, as hex strings. Each field feeds one role of the Qt palette."""

    window: str
    window_text: str
    base: str
    alternate_base: str
    text: str
    placeholder_text: str
    button: str
    button_text: str
    highlight: str
    highlighted_text: str
    link: str
    tool_tip_base: str
    tool_tip_text: str
    disabled_text: str


LIGHT_COLORS: ThemeColors = ThemeColors(
    window="#f2f3f5",
    window_text="#1f2328",
    base="#ffffff",
    alternate_base="#f6f8fa",
    text="#1f2328",
    placeholder_text="#8b949e",
    button="#e6e8eb",
    button_text="#1f2328",
    highlight="#3b6ea5",
    highlighted_text="#ffffff",
    link="#2a5d9f",
    tool_tip_base="#fbfbfb",
    tool_tip_text="#1f2328",
    disabled_text="#9aa1a9",
)

DARK_COLORS: ThemeColors = ThemeColors(
    window="#2b2d31",
    window_text="#dcdfe4",
    base="#1f2023",
    alternate_base="#26282c",
    text="#dcdfe4",
    placeholder_text="#7d838c",
    button="#383b41",
    button_text="#dcdfe4",
    highlight="#4b7fb8",
    highlighted_text="#ffffff",
    link="#6ea8e0",
    tool_tip_base="#383b41",
    tool_tip_text="#dcdfe4",
    disabled_text="#707680",
)

THEME_COLORS: dict[Theme, ThemeColors] = {Theme.LIGHT: LIGHT_COLORS, Theme.DARK: DARK_COLORS}
DEFAULT_THEME: Theme = Theme.DARK  # the theme the application starts with
