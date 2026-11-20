"""
The content of each stage of the analysis pipeline, shown in the right column.

    roi_inspector                 1. cropping and region of interest
    preprocessing_section         2. preprocessing of the volume
    blob_detection_inspector      3. blob detection
    trajectory_linking_inspector  4. tracking and linking
    batch_inspector               5. batch and export
"""

from apkit4d.gui.views.stages.base import StageInspectorView

__all__ = ["StageInspectorView"]
