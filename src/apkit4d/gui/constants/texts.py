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
STATUS_OPENING: str = "Opening {name}..."
STATUS_OPENED: str = "{path} | frames: {frames}"
STATUS_OPEN_FAILED: str = "Cannot open {name}: {reason}"
STATUS_INVALID_VOXEL: str = "Cannot show {name}: invalid voxel size {voxel}"
STATUS_FRAME_FAILED: str = "Cannot read frame {frame}: {reason}"
STATUS_NOT_3D: str = "Cannot show frame {frame}: expected a 3D volume, got shape {shape}"
STATUS_EMPTY_VOLUME: str = "Cannot show frame {frame}: the volume is empty"
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

# right panel and accordion
BUTTON_TOGGLE_ALL: str = "Toggle All"
TOOLTIP_TOGGLE_ALL: str = "Toggle collapse/expand state of all accordion sections"
TOOLTIP_STATS_TOGGLE: str = "Toggle statistics details"

# pipeline stage controls
LABEL_STAGE_VALUE: str = "Parameter:"
BUTTON_PLAN_UP_TO: str = "Plan up to this"
TOOLTIP_PLAN_UP_TO: str = "Plan execution up to this stage"
BUTTON_COMPLETE_STAGE: str = "Complete this"
TOOLTIP_COMPLETE_STAGE: str = "Mark this stage as completed"

# pipeline stages titles
STAGE_TITLE_ROI: str = "1 · Cropping & ROI"
STAGE_TITLE_PREPROCESSING: str = "2 · Preprocessing"
STAGE_TITLE_DETECTION: str = "3 · Blob Detection"
STAGE_TITLE_TRACKING: str = "4 · Tracking & Linking"
STAGE_TITLE_BATCH: str = "5 · Batch & Export"

# bottom stats text
STATS_ARROW_EXPANDED: str = "▼"
STATS_ARROW_COLLAPSED: str = "▲"
STATS_DEFAULT_SUMMARY: str = "Pipeline: Idle"
STATS_DEFAULT_DETAILS: str = "Ready to configure and run stages."
STATS_INITIAL_SUMMARY: str = "Working: 15%"
STATS_INITIAL_DETAILS: str = "Task: Processing Volume Data\nProgress: 15%\nElapsed: 00:01:24\nStatus: Active"
STATS_WORKING_SUMMARY: str = "Working: {step}..."
STATS_WORKING_DETAILS: str = (
    "Active Step: {step}\nStatus: In Progress\nTarget: {target}\nCompleted: {completed}"
)
STATS_COMPLETED_PROGRESS_SUMMARY: str = "Completed: {completed} / {total} stages"
STATS_COMPLETED_PROGRESS_DETAILS: str = (
    "Stages Completed ({completed_count}/{total}): {completed_stages}\nStatus: Idle"
)
STATS_COMPLETED_SUMMARY: str = "Pipeline: Completed"
STATS_COMPLETED_DETAILS: str = "All 5 pipeline stages are complete."
