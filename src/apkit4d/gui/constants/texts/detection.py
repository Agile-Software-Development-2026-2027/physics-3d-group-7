"""
Texts of the blob detection stage (3).
"""

# blob detection inspector
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
INSPECTOR_STATUS_DETECTING = "detecting blobs..."
INSPECTOR_STATUS_NO_BLOBS_FOUND = "frame {frame}: no blobs found"
INSPECTOR_STATUS_BLOBS_FOUND = "frame {frame}: {count} blobs (median volume {volume:.0f} µm³)"
INSPECTOR_STATUS_DETECTION_FAILED = "detection failed: {reason}"
INSPECTOR_BUTTON_DISABLED_INFO = "\u24d8 Normalize the volume to enable this button."
INSPECTOR_CHECKBOX_DISABLED_INFO = "\u24d8 Normalize the volume to enable this checkbox."
DETECTION_REQUIRES_NORMALIZATION = (
    "Enable intensity normalization in Preprocessing before running blob detection."
)
