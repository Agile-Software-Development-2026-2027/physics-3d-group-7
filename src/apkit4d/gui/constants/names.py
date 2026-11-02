"""
Object names of the components.

The tests find the components with `findChild(type, name)`, so every component that a test needs
has a name here.
"""

# main window
STATUS_BAR: str = "status_bar"
FILE_MENU: str = "file_menu"
OPEN_ACTION: str = "open_action"
QUIT_ACTION: str = "quit_action"
COLUMNS_SPLITTER: str = "columns_splitter"

# panels
LEFT_PANEL: str = "left_panel"
CENTER_PANEL: str = "center_panel"
CENTER_PLACEHOLDER: str = "center_placeholder"
RIGHT_PANEL: str = "right_panel"

# playback bar
PLAYBACK_BAR: str = "playback_bar"
PREVIOUS_BUTTON: str = "previous_button"
PLAY_BUTTON: str = "play_button"
NEXT_BUTTON: str = "next_button"
FRAME_SLIDER: str = "frame_slider"

# controls of the side panels
THEME_BUTTON: str = "theme_button"
