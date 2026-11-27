"""
Texts of the ROI stage (1).
"""

# roi inspector
INSPECTOR_SECTION_ROI_BOUNDS: str = "Region of Interest (µm)"
INSPECTOR_LABEL_ROI_X: str = "X range (µm)"
INSPECTOR_LABEL_ROI_Y: str = "Y range (µm)"
INSPECTOR_LABEL_ROI_Z: str = "Z range (µm)"
ROI_MIN_LABEL: str = "min"
ROI_MAX_LABEL: str = "max"
INSPECTOR_TOOLTIP_ROI_BOUNDS: str = "Spatial bounds of the Region of Interest in micrometers."
INSPECTOR_BUTTON_SELECT_ROI: str = "Select ROI on 3D View"
INSPECTOR_TOOLTIP_SELECT_ROI: str = "Click and drag directly on the 3D volume to draw a Region of Interest."
INSPECTOR_BUTTON_ACCEPT_ROI: str = "Accept"
INSPECTOR_TOOLTIP_ACCEPT_ROI: str = "Confirm the selected Region of Interest and crop the volume."
INSPECTOR_BUTTON_CANCEL_ROI: str = "Cancel"
INSPECTOR_TOOLTIP_CANCEL_ROI: str = "Cancel ROI selection and discard preview changes."
INSPECTOR_BUTTON_RESET_ROI: str = "Reset to defaults"
INSPECTOR_TOOLTIP_RESET_ROI: str = "Remove cropping and restore the full 3D volume."
INSPECTOR_STATUS_ROI_FULL: str = "Full volume active (no ROI cropping)"
INSPECTOR_STATUS_ROI_SELECTING: str = "Click and drag on the 3D volume, or adjust coordinates..."
INSPECTOR_STATUS_ROI_ACTIVE: str = (
    "Active ROI: X=[{x0:.1f}, {x1:.1f}] Y=[{y0:.1f}, {y1:.1f}] Z=[{z0:.1f}, {z1:.1f}] µm"
)
INSPECTOR_BUTTON_UNDO_ROI: str = "Undo Last Crop"
INSPECTOR_TOOLTIP_UNDO_ROI: str = "Revert to the previous Region of Interest before the last accepted crop."
INSPECTOR_BUTTON_SAVE_ROI: str = "Save ROI"
INSPECTOR_TOOLTIP_SAVE_ROI: str = (
    "Save the current Region of Interest in a certain range of frames to a file."
)
INSPECTOR_LABEL_SELECT_FRAMES: str = "Select frames:"
