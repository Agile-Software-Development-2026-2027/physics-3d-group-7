"""Unified processing pipeline data contracts and protocols."""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from apkit4d.image import Image
from apkit4d.preprocessing import PreprocParams
from apkit4d.roi import Origin3D, VoxelSize3D

type ProgressCallback = Callable[[int, int, str], None]


class CancelToken(Protocol):
    """Cooperative cancellation contract for background tasks."""

    @property
    def is_cancelled(self) -> bool: ...


@dataclass(frozen=True)
class CroppedFrame:
    """Output of Stage 1 (ROI Cropping) for a single frame."""

    frame: int
    raw_roi_volume: Image[np.float32]
    voxel_um: VoxelSize3D
    origin_xyz_um: Origin3D
    voxel_offset_zyx: tuple[int, int, int]


@dataclass(frozen=True)
class PreprocessedFrame:
    """Output of Stage 2 (Preprocessing) for a single frame."""

    cropped: CroppedFrame
    image: Image[np.float32]
    params: PreprocParams

    @property
    def is_normalized(self) -> bool:
        """Whether intensity normalization was enabled during preprocessing."""
        return self.params.normalization_enabled


@dataclass(frozen=True)
class FrameDetectionResult:
    """Output of Stage 3 (Blob Detection) for a single frame."""

    frame: int
    detections: pd.DataFrame
    seeds_response: NDArray[np.float32] = field(default_factory=lambda: np.empty(0, dtype=np.float32))
    labels: Image[np.int32] | None = None


# Maybe: Stage 4 (Linking)
# Maybe: Stage 5 (Export)


@dataclass(frozen=True)
class SequenceDetectionResult:
    """Unified output of multi-frame blob detection across [t0, t1]."""

    detections: pd.DataFrame | None
    table_path: Path | None
    params_path: Path | None
    num_blobs: int
    num_frames: int
    metadata: dict[str, Any]


class DetectionSink(Protocol):
    """Destination strategy for multi-frame blob detection results (RAM, disk, or both)."""

    def on_frame_detections(self, frame: int, df: pd.DataFrame) -> None: ...

    def finalize(self, metadata: dict[str, Any]) -> SequenceDetectionResult: ...
