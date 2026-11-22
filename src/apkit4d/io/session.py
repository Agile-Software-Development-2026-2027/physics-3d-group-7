"""Domain models and protocols for precomputed/loaded analysis sessions."""

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import pandas as pd
from numpy.typing import NDArray

from apkit4d.core.models import DetectionConfig, PreprocessingConfig, TrackingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.io.czi import CziInfo
from apkit4d.tracking.linker import TrackingResult

_BLOB_REQUIRED_COLUMNS: tuple[str, ...] = ("frame", "x_um", "y_um", "z_um")


@dataclass(frozen=True)
class PrecomputedSession:
    """Precomputed analysis results attached to a recording or loaded from disk.

    This container decouples GUI visualization and pipeline hydration from how the data was
    obtained, supporting synthetic `--mock` recordings now and saved JSON/Parquet/CSV sessions
    in the future.

    Attributes:
        blobs: Optional per-frame detections table containing centroid coordinates.
        tracking: Optional trajectory-linking result containing linked tracks and stats.
        roi: Optional region of interest active for the precomputed outputs.
        preproc_params: Optional preprocessing parameters associated with the session.
        blob_params: Optional blob-detection parameters associated with the session.
        tracking_config: Optional tracking configuration associated with the session.
        completed_steps: Explicit pipeline step identifiers already completed. When ``None``,
            completed stages are inferred automatically from present artifacts.
    """

    blobs: pd.DataFrame | None = None
    tracking: TrackingResult | None = None
    roi: RegionOfInterest | None = None
    preproc_params: PreprocessingConfig | None = None
    blob_params: DetectionConfig | None = None
    tracking_config: TrackingConfig | None = None
    completed_steps: tuple[str, ...] | None = None

    @property
    def effective_blobs(self) -> pd.DataFrame | None:
        """Return explicit blobs or derive per-frame blobs from tracking rows when available."""
        if self.blobs is not None:
            return self.blobs
        if self.tracking is not None and _has_blob_columns(self.tracking.tracks):
            return self.tracking.tracks
        return None


def _has_blob_columns(df: pd.DataFrame) -> bool:
    return set(_BLOB_REQUIRED_COLUMNS).issubset(df.columns)


def infer_completed_steps(session: PrecomputedSession) -> tuple[str, ...]:
    """Return ordered pipeline stage identifiers satisfied by `session`.

    When `session.completed_steps` is omitted, stages are inferred as a continuous prefix so
    downstream pipeline invariants always hold.
    """
    if session.completed_steps is not None:
        return session.completed_steps
    if session.tracking is not None:
        return ("roi", "preprocessing", "detection", "tracking")
    if session.blobs is not None:
        return ("roi", "preprocessing", "detection")
    if session.preproc_params is not None:
        return ("roi", "preprocessing")
    if session.roi is not None:
        return ("roi",)
    return ()


@runtime_checkable
class PrecomputedSource(Protocol):
    """A frame source that also carries precomputed detection/tracking session state."""

    @property
    def info(self) -> CziInfo: ...

    @property
    def session(self) -> PrecomputedSession: ...

    def read(self, t: int) -> NDArray[Any]: ...

    def close(self) -> None: ...


class PrecomputedFrameSource:
    """Adapter pairing any base frame source with a `PrecomputedSession`."""

    def __init__(self, base: Any, session: PrecomputedSession) -> None:
        self._base = base
        self._session = session

    @property
    def info(self) -> CziInfo:
        """Acquisition metadata delegated from the underlying source."""
        return self._base.info

    @property
    def session(self) -> PrecomputedSession:
        """Precomputed session data associated with the underlying source."""
        return self._session

    def read(self, t: int) -> NDArray[Any]:
        """Read frame `t` from the underlying frame source."""
        return self._base.read(t)

    def close(self) -> None:
        """Close the underlying frame source."""
        self._base.close()
