"""
Constants shared by the GUI.

Every value that more than one file needs, or that someone may want to change, lives here:
sizes, texts, shortcuts and object names. The object names are how the tests find the
components with `findChild`.
"""

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

# playback
FRAME_INTERVAL_MS: int = 100  # time between two frames while the recording is playing
