"""
Texts of the right column: stage titles, stage controls and statistics.
"""

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
