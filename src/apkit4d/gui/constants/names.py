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

# right panel controls and containers
RIGHT_PANEL_TOP_BAR: str = "right_panel_top_bar"
TOGGLE_ALL_BUTTON: str = "toggle_all_button"
SCROLL_CONTENT: str = "accordion_scroll_content"
MODERN_SCROLL_AREA: str = "modernScrollArea"

# pipeline stage controls
STAGE_NUMBER_FIELD: str = "stage_number_field"
PLAN_UP_TO_BUTTON: str = "plan_up_to_button"
COMPLETE_STAGE_BUTTON: str = "complete_stage_button"

# bottom stats section
BOTTOM_STATS_SECTION: str = "bottom_stats_section"
BOTTOM_STATS_HEADER: str = "bottom_stats_header"
BOTTOM_STATS_SUMMARY_LABEL: str = "bottom_stats_summary_label"
BOTTOM_STATS_TOGGLE_BUTTON: str = "bottom_stats_toggle_button"
BOTTOM_STATS_DETAILS_FRAME: str = "bottom_stats_details_frame"
BOTTOM_STATS_DETAILS_LABEL: str = "bottom_stats_details_label"

# accordion component
ACCORDION_TOGGLE_BUTTON: str = "accordion_toggle_button"
ACCORDION_CONTENT_AREA: str = "accordion_content_area"
