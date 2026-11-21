"""
Texts of the blob detection stage (3).
"""

# blob detection inspector
INSPECTOR_LABEL_FRAME_RANGE: str = "Frame range"
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
INSPECTOR_STATUS_DETECTING = "detecting blobs..."
INSPECTOR_STATUS_NO_BLOBS_FOUND = "frame {frame}: no blobs found"
INSPECTOR_STATUS_BLOBS_FOUND = "frame {frame}: {count} blobs (median volume {volume:.0f} µm³)"
INSPECTOR_STATUS_DETECTION_FAILED = "detection failed: {reason}"
INSPECTOR_BUTTON_DISABLED_INFO = "\u24d8 Normalize the volume to enable this button."
INSPECTOR_CHECKBOX_DISABLED_INFO = "\u24d8 Normalize the volume to enable this checkbox."
