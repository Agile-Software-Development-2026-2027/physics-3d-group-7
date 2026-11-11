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
FRAME_COUNTER: str = "frame_counter"

# controls of the side panels
THEME_BUTTON: str = "theme_button"
APPEARANCE_SECTION: str = "appearance_section"
LAYERS_SECTION: str = "layers_section"

# right panel controls and containers
RIGHT_PANEL_TOP_BAR: str = "right_panel_top_bar"
TOGGLE_ALL_BUTTON: str = "toggle_all_button"
SCROLL_CONTENT: str = "accordion_scroll_content"
MODERN_SCROLL_AREA: str = "modernScrollArea"

# pipeline stage controls
STAGE_NUMBER_FIELD: str = "stage_number_field"
PLAN_UP_TO_BUTTON: str = "plan_up_to_button"
COMPLETE_STAGE_BUTTON: str = "complete_stage_button"

# preprocessing stage controls
PREPROC_DENOISE_XY_FIELD: str = "preproc_denoise_xy_field"
PREPROC_DENOISE_Z_FIELD: str = "preproc_denoise_z_field"
PREPROC_BG_MODE_COMBO: str = "preproc_bg_mode_combo"
PREPROC_BG_PERCENTILE_FIELD: str = "preproc_bg_percentile_field"
PREPROC_BG_SIGMA_XY_FIELD: str = "preproc_bg_sigma_xy_field"
PREPROC_NORMALIZATION_ENABLED_FIELD: str = "preproc_normalization_enabled"
PREPROC_LOWEST_INTENSITY_FIELD: str = "preproc_lowest_intensity_field"
PREPROC_HIGHEST_INTENSITY_FIELD: str = "preproc_highest_intensity_field"
PREPROC_LOG_COMPRESSION_CHECKBOX: str = "preproc_log_compression_checkbox"
PREPROC_GAMMA_FIELD: str = "preproc_gamma_field"
PREPROC_CLAHE_CHECKBOX: str = "preproc_clahe_checkbox"
PREPROC_CLAHE_CLIP_FIELD: str = "preproc_clahe_clip_field"
PREPROC_CLAHE_KERNEL_XY_FIELD: str = "preproc_clahe_kernel_xy_field"

# bottom stats section
BOTTOM_STATS_SECTION: str = "bottom_stats_section"
BOTTOM_STATS_HEADER: str = "bottom_stats_header"
BOTTOM_STATS_SUMMARY_LABEL: str = "bottom_stats_summary_label"
BOTTOM_STATS_TOGGLE_BUTTON: str = "bottom_stats_toggle_button"
BOTTOM_STATS_DETAILS_FRAME: str = "bottom_stats_details_frame"
BOTTOM_STATS_DETAILS_LABEL: str = "bottom_stats_details_label"

# accordion component
ACCORDION_HEADER_FRAME: str = "accordion_header_frame"
ACCORDION_TOGGLE_BUTTON: str = "accordion_toggle_button"
PLAY_STAGE_BUTTON: str = "play_stage_button"
ACCORDION_CONTENT_AREA: str = "accordion_content_area"

# blob detection inspector
DETECTION_INSPECTOR_STEP = "detection_inspector_step"

DETECTION_INSPECTOR_BATCH_PROCESSING_GROUP = "detection_inspector_batch_processing_group"
DETECTION_INSPECTOR_DETECTION_PARAMETERS_GROUP = "detection_inspector_detection_parameters_group"

DETECTION_INSPECTOR_FRAME_START = "detection_inspector_frame_start"
DETECTION_INSPECTOR_FRAME_END = "detection_inspector_frame_end"
DETECTION_INSPECTOR_OUTPUT_FOLDER = "detection_inspector_output_folder"
DETECTION_INSPECTOR_OUTPUT_BROWSE_BUTTON = "detection_inspector_output_browse_button"
DETECTION_INSPECTOR_WORKERS = "detection_inspector_workers"
DETECTION_INSPECTOR_OUTPUT_FORMAT = "detection_inspector_output_format"

DETECTION_INSPECTOR_DIAMETER_XY = "detection_inspector_diameter_xy"
DETECTION_INSPECTOR_DIAMETER_Z = "detection_inspector_diameter_z"
DETECTION_INSPECTOR_DIAMETER_Z_EQUALS_XY = "detection_inspector_diameter_z_equals_xy"
DETECTION_INSPECTOR_LOG_THRESHOLD = "detection_inspector_log_threshold"
DETECTION_INSPECTOR_SEED_SEPARATION = "detection_inspector_seed_separation"
DETECTION_INSPECTOR_BOUNDARY = "detection_inspector_boundary"
DETECTION_INSPECTOR_MIN_VOLUME = "detection_inspector_min_volume"
DETECTION_INSPECTOR_MAX_VOLUME = "detection_inspector_max_volume"

DETECTION_INSPECTOR_UPDATE_ON_CHANGE = "detection_inspector_update_on_change"
DETECTION_INSPECTOR_SHOW_SEGMENTS = "detection_inspector_show_segments"
DETECTION_INSPECTOR_FIND_BLOBS_BUTTON = "detection_inspector_find_blobs_button"
DETECTION_INSPECTOR_DETECTION_STATUS = "detection_inspector_detection_status"
