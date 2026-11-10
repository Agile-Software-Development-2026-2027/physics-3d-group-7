"""
Every text shown to the user.

Texts with `{...}` are templates: fill them with `str.format`.
"""

from typing import assert_never

from apkit4d.gui.constants.application import CZI_SUFFIX
from apkit4d.gui.models.output_type import OutputType

# center panel
PLACEHOLDER: str = f"Open a {CZI_SUFFIX} file to start (File > Open)"

# main window
WINDOW_TITLE_WITH_FILE: str = "{name} - {app}"
STATUS_NO_FILE: str = "No file open"
STATUS_OPENING: str = "Opening {name}..."
STATUS_OPENED: str = "{path}"
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
TOOLTIP_PREVIOUS: str = "Previous frame"
TOOLTIP_PLAY: str = "Play"
TOOLTIP_PAUSE: str = "Pause"
TOOLTIP_NEXT: str = "Next frame"
COUNTER_SEPARATOR: str = " / "
COUNTER_EMPTY: str = "–"  # shown instead of the numbers when there is no recording

# side panels
SECTION_APPEARANCE: str = "Appearance"
SECTION_LAYERS: str = "Layers"
LAYERS_EMPTY: str = "No layers yet"
BUTTON_THEME: str = "Switch theme"
RIGHT_PANEL_PLACEHOLDER: str = "RIGHT PANEL"  # temporary, until the right panel has its controls

# right panel and accordion
BUTTON_TOGGLE_ALL: str = "Toggle All"
TOOLTIP_TOGGLE_ALL: str = "Toggle collapse/expand state of all accordion sections"
TOOLTIP_STATS_TOGGLE: str = "Toggle statistics details"

# pipeline stage controls
LABEL_STAGE_VALUE: str = "Parameter:"
BUTTON_PLAY_STAGE: str = "▶"
TOOLTIP_PLAY_STAGE: str = "Run pipeline up to this stage"
BUTTON_PLAN_UP_TO: str = "Plan up to this"
TOOLTIP_PLAN_UP_TO: str = "Plan execution up to this stage"
BUTTON_COMPLETE_STAGE: str = "Complete this"
TOOLTIP_COMPLETE_STAGE: str = "Mark this stage as completed"

# preprocessing stage controls
LABEL_PREPROC_DENOISE_XY: str = "Denoise XY (µm):"
LABEL_PREPROC_DENOISE_Z: str = "Denoise Z (µm):"
LABEL_PREPROC_BG_MODE: str = "Background Mode:"
LABEL_PREPROC_BG_PERCENTILE: str = "BG Percentile (%):"
LABEL_PREPROC_BG_SIGMA_XY: str = "BG Sigma XY (µm):"
LABEL_PREPROC_LOWEST_INTENSITY: str = "Window Min (AU):"
LABEL_PREPROC_HIGHEST_INTENSITY: str = "Window Max (AU):"
LABEL_PREPROC_LOG_COMPRESSION: str = "Logarithmic Compression"
LABEL_PREPROC_GAMMA: str = "Gamma Correction:"
LABEL_PREPROC_CLAHE: str = "CLAHE Enhancement"
LABEL_PREPROC_CLAHE_CLIP: str = "CLAHE Clip Limit:"
LABEL_PREPROC_CLAHE_KERNEL_XY: str = "CLAHE Kernel XY (µm):"

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


# output types labels
def get_output_type_label(output_type: OutputType) -> str:
    match output_type:
        case OutputType.PARQUET:
            return "Parquet"
        case OutputType.CSV:
            return "CSV"
        case _:
            assert_never(output_type)


# blob detection inspector
INSPECTOR_LABEL_FRAME_RANGE: str = "Frame range"
START_TIME_LABEL: str = "t₀"
END_TIME_LABEL: str = "t₁"
INSPECTOR_TOOLTIP_FRAME_RANGE: str = "The frames range used by batch and linking (0-based, inclusive)."

INSPECTOR_SECTION_DETECTION_PARAMETERS: str = "Detection parameters"
INSPECTOR_LABEL_DIAMETER_XY: str = "Diameter XY (µm)"
INSPECTOR_TOOLTIP_DIAMETER_XY: str = "Expected cell diameter in X and Y."
INSPECTOR_LABEL_DIAMETER_Z: str = "Diameter Z (µm)"
INSPECTOR_TOOLTIP_DIAMETER_Z: str = (
    "Expected extent in Z. Much larger than the real cell,\n because the axial PSF stretches it."
)

INSPECTOR_LABEL_DIAMETER_Z_EQUALS_XY: str = "Diameter Z = Diameter XY"
INSPECTOR_TOOLTIP_DIAMETER_Z_EQUALS_XY: str = "Use a single diameter for all axes."
INSPECTOR_LABEL_LOG_THRESHOLD: str = "LoG threshold"
INSPECTOR_TOOLTIP_LOG_THRESHOLD: str = "Minimum LoG response for a candidate to count. Higher = fewer blobs."
INSPECTOR_LABEL_SEED_SEPARATION: str = "Seed separation (× diameter)"
INSPECTOR_TOOLTIP_SEED_SEPARATION: str = (
    "Minimum distance between two candidates,\n as a fraction of the diameter."
)
INSPECTOR_LABEL_BOUNDARY: str = "Boundary (× peak)"
INSPECTOR_TOOLTIP_BOUNDARY: str = (
    "Each region keeps the voxels above this fraction of its own peak\n. Lower = larger blobs."
)
INSPECTOR_LABEL_MIN_VOLUME: str = "Min volume (µm³)"
INSPECTOR_TOOLTIP_MIN_VOLUME: str = "Discard blobs smaller than this."
INSPECTOR_LABEL_MAX_VOLUME: str = "Max volume (µm³)"
INSPECTOR_TOOLTIP_MAX_VOLUME: str = "Discard blobs larger than this."

INSPECTOR_LABEL_UPDATE_ON_CHANGE: str = "Update blobs on every change"
INSPECTOR_TOOLTIP_UPDATE_ON_CHANGE: str = (
    "Compute blobs on every parameter or frame change,\n even before pressing Find blobs."
)
INSPECTOR_LABEL_SHOW_SEGMENTS: str = "Show segments"
INSPECTOR_TOOLTIP_SHOW_SEGMENTS: str = (
    "Add a segments layer with the watershed regions.\n Toggling it recomputes the blobs."
)
INSPECTOR_BUTTON_FIND_BLOBS: str = "Find blobs (current frame)"
INSPECTOR_TOOLTIP_FIND_BLOBS: str = (
    "Run preprocessing and blob detection on the current\n "
    "frame, using the current ROI and parameters.\n "
    "Nothing is saved to file."
)
INSPECTOR_STATUS_NO_BLOBS: str = "No blobs detected"

INSPECTOR_SECTION_BATCH_PROCESSING: str = "Batch Processing"
INSPECTOR_PLACEHOLDER_OUTPUT_FOLDER: str = "Choose output folder"
INSPECTOR_DIALOG_OUTPUT_FOLDER: str = "Choose output folder"
INSPECTOR_LABEL_OUTPUT_FOLDER: str = "Output folder"
INSPECTOR_LABEL_WORKERS: str = "Workers"
INSPECTOR_LABEL_FORMAT: str = "Format"
INSPECTOR_BUTTON_RUN_BATCH: str = "Run batch t₀..t₁"
INSPECTOR_TOOLTIP_RUN_BATCH: str = (
    "Run detection on every frame from t0 to t1,\n "
    "using the current ROI and detection parameters.\n "
    "Runs in a separate process."
)
