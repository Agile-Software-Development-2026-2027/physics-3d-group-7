"""
Constants shared by the GUI.

Every value that more than one file needs, or that someone may want to change, lives here:
sizes, texts, shortcuts, colors and object names. The object names are how the tests find the
components with `findChild`.
"""

from dataclasses import dataclass
from enum import Enum

# application
APP_NAME: str = "ApKit4D"
CZI_SUFFIX: str = ".czi"

# window geometry
WINDOW_WIDTH: int = 1200
WINDOW_HEIGHT: int = 800
SIDE_PANEL_WIDTH: int = 200  # initial width of the side columns
SIDE_PANEL_MIN_WIDTH: int = 120  # narrower than this, a side column collapses

# columns of the main window, from left to right: left panel, central column, right panel
COLUMN_SIZES: tuple[int, int, int] = (
    SIDE_PANEL_WIDTH,
    WINDOW_WIDTH - 2 * SIDE_PANEL_WIDTH,
    SIDE_PANEL_WIDTH,
)
COLUMN_COLLAPSIBLE: tuple[bool, bool, bool] = (True, False, True)  # the 3D view never disappears
COLUMN_STRETCH: tuple[int, int, int] = (0, 1, 0)  # when the window is resized, only the center changes

# playback
FRAME_INTERVAL_MS: int = 100  # time between two frames while the recording is playing


# themes
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
DEFAULT_THEME: Theme = Theme.DARK  # dark theme is the default one because I like it better
STYLE_NAME: str = "Fusion"  # looks the same on every operating system and follows the palette

# style sheet shared by all the themes: it only uses colors of the current palette
STYLESHEET: str = """
QSplitter::handle { background-color: palette(mid); }
QSplitter::handle:horizontal { width: 4px; }
QSplitter::handle:hover { background-color: palette(highlight); }
"""

# texts shown to the user
TEXT_PLACEHOLDER: str = f"Open a {CZI_SUFFIX} file to start (File > Open)"
TEXT_WINDOW_TITLE_WITH_FILE: str = "{name} - {app}"
TEXT_STATUS_NO_FILE: str = "No file open"
TEXT_STATUS_NOT_CZI: str = f"Not a {CZI_SUFFIX} file: {{name}}"
TEXT_STATUS_NOT_FOUND: str = "File not found: {path}"
TEXT_FILE_DIALOG_TITLE: str = f"Open a {CZI_SUFFIX} file"
TEXT_FILE_DIALOG_FILTER: str = f"CZI files (*{CZI_SUFFIX})"
TEXT_MENU_FILE: str = "&File"
TEXT_ACTION_OPEN: str = "&Open..."
TEXT_ACTION_QUIT: str = "&Quit"
TEXT_BUTTON_PREVIOUS: str = "<"
TEXT_BUTTON_PLAY: str = "Play"
TEXT_BUTTON_PAUSE: str = "Pause"
TEXT_BUTTON_NEXT: str = ">"
TEXT_BUTTON_THEME: str = "Switch theme"

# keyboard shortcuts
SHORTCUT_OPEN: str = "Ctrl+O"
SHORTCUT_QUIT: str = "Ctrl+Q"

# object names
NAME_STATUS_BAR: str = "status_bar"
NAME_FILE_MENU: str = "file_menu"
NAME_OPEN_ACTION: str = "open_action"
NAME_QUIT_ACTION: str = "quit_action"
NAME_COLUMNS_SPLITTER: str = "columns_splitter"
NAME_LEFT_PANEL: str = "left_panel"
NAME_CENTRAL_COLUMN: str = "central_column"
NAME_RIGHT_PANEL: str = "right_panel"
NAME_CENTRAL_PLACEHOLDER: str = "central_placeholder"
NAME_PLAYBACK_BAR: str = "playback_bar"
NAME_PREVIOUS_BUTTON: str = "previous_button"
NAME_PLAY_BUTTON: str = "play_button"
NAME_NEXT_BUTTON: str = "next_button"
NAME_FRAME_SLIDER: str = "frame_slider"
NAME_THEME_BUTTON: str = "theme_button"
