"""Unified processing pipeline contracts and pure stage functions.

Note:
    Apparently we used this in other modules so I will use it too...
"""

from apkit4d.pipeline.contracts import (
    CancelToken,
    CroppedFrame,
    DetectionSink,
    FrameDetectionResult,
    PreprocessedFrame,
    ProgressCallback,
    SequenceDetectionResult,
)
from apkit4d.pipeline.frame_stages import (
    coerce_blob_params,
    coerce_preproc_params,
    coerce_roi,
    crop_frame,
    detect_blobs_in_frame,
    preprocess_frame,
)

__all__ = [
    "CancelToken",
    "CroppedFrame",
    "DetectionSink",
    "FrameDetectionResult",
    "PreprocessedFrame",
    "ProgressCallback",
    "SequenceDetectionResult",
    "coerce_blob_params",
    "coerce_preproc_params",
    "coerce_roi",
    "crop_frame",
    "detect_blobs_in_frame",
    "preprocess_frame",
]
