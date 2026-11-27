"""
Texts of the batch and export stage (5).
"""

from typing import assert_never

from apkit4d.gui.models.output_type import OutputType


# output types labels
def get_output_type_label(output_type: OutputType) -> str:
    match output_type:
        case OutputType.PARQUET:
            return "Parquet"
        case OutputType.CSV:
            return "CSV"
        case _:
            assert_never(output_type)


# batch output
BATCH_OUTPUT: str = "Output folder"
BATCH_BROWSE: str = "Browse..."
BATCH_FORMAT: str = "Table format"
BATCH_FRAMES: str = "Frames to export"
BATCH_FRAMES_TOOLTIP: str = "Frames to save, both ends included."
BATCH_NO_SOURCE: str = "Open a CZI file to run batch processing."
BATCH_READY: str = (
    "Results are saved automatically. Existing output files in this folder will be overwritten."
)
BATCH_WORKING: str = "Saving processed pipeline results..."
BATCH_ERROR_TITLE: str = "Batch failed"
BATCH_FAILED: str = "Batch failed: {reason}"
BATCH_SAVED: str = "Saved {blobs} detections from {frames} frames.\nTable: {table}\nParameters: {params}"
BATCH_EMPTY: str = (
    "No detections found in {frames} frames. No CSV/Parquet file was created.\nParameters: {params}"
)
BATCH_COMPLETE: str = "Batch completed"
BATCH_PROGRESS: str = "Working: Batch — {done}/{total} detections"
