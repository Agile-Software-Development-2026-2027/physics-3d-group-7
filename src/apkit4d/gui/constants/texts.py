"""
Every text shown to the user.

Texts with `{...}` are templates: fill them with `str.format`.
"""

from apkit4d.gui.constants.application import CZI_SUFFIX

# center panel
PLACEHOLDER: str = f"Open a {CZI_SUFFIX} file to start (File > Open)"

# main window
WINDOW_TITLE_WITH_FILE: str = "{name} - {app}"
STATUS_NO_FILE: str = "No file open"
STATUS_NOT_CZI: str = f"Not a {CZI_SUFFIX} file: {{name}}"
STATUS_NOT_FOUND: str = "File not found: {path}"
FILE_DIALOG_TITLE: str = f"Open a {CZI_SUFFIX} file"
FILE_DIALOG_FILTER: str = f"CZI files (*{CZI_SUFFIX})"

# menus
MENU_FILE: str = "&File"
ACTION_OPEN: str = "&Open..."
ACTION_QUIT: str = "&Quit"

# playback bar
BUTTON_PREVIOUS: str = "<"
BUTTON_PLAY: str = "Play"
BUTTON_PAUSE: str = "Pause"
BUTTON_NEXT: str = ">"

# side panels
BUTTON_THEME: str = "Switch theme"
RIGHT_PANEL_PLACEHOLDER: str = "RIGHT PANEL"  # temporary, until the right panel has its controls
