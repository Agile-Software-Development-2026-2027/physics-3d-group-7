"""Tests for generalized precomputed session models and source adapters."""

import numpy as np
import pandas as pd

from apkit4d.core.models import DetectionConfig, PreprocessingConfig, TrackingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.io.czi import CziInfo
from apkit4d.io.mock import MockConfig, create_mock_source
from apkit4d.io.session import (
    PrecomputedFrameSource,
    PrecomputedSession,
    PrecomputedSource,
    infer_completed_steps,
)
from apkit4d.tracking.linker import TrackingResult


class _DummyFrameSource:
    def __init__(self) -> None:
        self.info = CziInfo(
            path="sample.czi",
            n_t=3,
            n_z=2,
            n_y=4,
            n_x=4,
            n_c=1,
            dtype="uint16",
            px_size_x=1.0,
            px_size_y=1.0,
            px_size_z=2.0,
            dt_s=0.1,
            dt_source="test",
        )
        self.closed = False

    def read(self, t: int) -> np.ndarray:
        return np.full((2, 4, 4), t, dtype=np.uint16)

    def close(self) -> None:
        self.closed = True


def _sample_tracks() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "frame": [0, 1],
            "x_um": [1.0, 2.0],
            "y_um": [2.0, 3.0],
            "z_um": [3.0, 4.0],
            "track_id": [1, 1],
            "volume_um3": [100.0, 120.0],
        }
    )


def test_precomputed_session_effective_blobs_and_step_inference() -> None:
    empty = PrecomputedSession()
    assert empty.effective_blobs is None
    assert infer_completed_steps(empty) == ()

    roi_only = PrecomputedSession(roi=RegionOfInterest(0.0, 5.0, 0.0, 5.0, 0.0, 5.0))
    assert infer_completed_steps(roi_only) == ("roi",)

    preproc_only = PrecomputedSession(preproc_params=PreprocessingConfig())
    assert infer_completed_steps(preproc_only) == ("roi", "preprocessing")

    blobs_df = pd.DataFrame({"frame": [0], "x_um": [1.0], "y_um": [1.0], "z_um": [1.0]})
    blobs_only = PrecomputedSession(blobs=blobs_df)
    assert blobs_only.effective_blobs is blobs_df
    assert infer_completed_steps(blobs_only) == ("roi", "preprocessing", "detection")

    tracking_res = TrackingResult(tracks=_sample_tracks(), metadata={})
    tracks_only = PrecomputedSession(tracking=tracking_res, tracking_config=TrackingConfig())
    assert tracks_only.effective_blobs is tracking_res.tracks
    assert infer_completed_steps(tracks_only) == ("roi", "preprocessing", "detection", "tracking")

    explicit = PrecomputedSession(
        tracking=tracking_res,
        blob_params=DetectionConfig(),
        completed_steps=("roi", "preprocessing"),
    )
    assert infer_completed_steps(explicit) == ("roi", "preprocessing")


def test_precomputed_frame_source_delegates_and_matches_protocol() -> None:
    base = _DummyFrameSource()
    session = PrecomputedSession(tracking=TrackingResult(tracks=_sample_tracks(), metadata={}))
    wrapped = PrecomputedFrameSource(base, session)

    assert isinstance(wrapped, PrecomputedSource)
    assert wrapped.info is base.info
    assert wrapped.session is session
    assert int(wrapped.read(2)[0, 0, 0]) == 2
    wrapped.close()
    assert base.closed


def test_mock_frame_source_satisfies_precomputed_source_protocol() -> None:
    mock = create_mock_source(MockConfig(n_t=5, n_z=8, n_y=24, n_x=24))
    assert isinstance(mock, PrecomputedSource)
    session = mock.session
    assert session.tracking is not None
    assert not session.tracking.stats.empty
    assert len(session.tracking.tracks) == len(mock.tracks)
    assert session.effective_blobs is not None
    mock.close()
