"""
Unit tests for core models and configuration.
This testign file is basically useless, it is only present to get to thew >= 80% coverage.
If this had failed we would have needed to avoid using pydantic validation.
I remembered teh final `.` here :) not gonna happen often.
"""

import pytest
from pydantic import ValidationError

from apkit4d.core.frame_range import FrameRange
from apkit4d.core.models import BatchConfig, RoiConfig, TrackingConfig
from apkit4d.core.roi import RegionOfInterest


def test_tracking_config_defaults() -> None:
    """
    Verify default parameters of TrackingConfig.
    """
    cfg = TrackingConfig()
    assert cfg.max_dist_um == 20.0
    assert cfg.max_gap == 3
    assert cfg.gap_dist_um == 25.0
    assert cfg.min_len == 5
    assert cfg.velocity_smoothing == 0.5
    assert cfg.mc_resamples == 20
    assert cfg.max_speed_um_s == 250.0


def test_tracking_config_custom_values() -> None:
    """
    Verify custom initialization of TrackingConfig.
    """
    cfg = TrackingConfig(
        max_dist_um=15.0,
        max_gap=5,
        gap_dist_um=30.0,
        min_len=4,
        velocity_smoothing=0.8,
        mc_resamples=50,
        max_speed_um_s=300.0,
    )
    assert cfg.max_dist_um == 15.0
    assert cfg.max_gap == 5
    assert cfg.gap_dist_um == 30.0
    assert cfg.min_len == 4
    assert cfg.velocity_smoothing == 0.8
    assert cfg.mc_resamples == 50
    assert cfg.max_speed_um_s == 300.0


def test_tracking_config_validation_errors() -> None:
    """
    Verify constraint validation on TrackingConfig.
    """
    with pytest.raises(ValidationError):
        TrackingConfig(max_dist_um=0.0)

    with pytest.raises(ValidationError):
        TrackingConfig(max_gap=-1)

    with pytest.raises(ValidationError):
        TrackingConfig(min_len=1)

    with pytest.raises(ValidationError):
        TrackingConfig(velocity_smoothing=-0.1)

    with pytest.raises(ValidationError):
        TrackingConfig(velocity_smoothing=1.5)

    with pytest.raises(ValidationError):
        TrackingConfig(mc_resamples=-1)


def test_tracking_config_frozen() -> None:
    """
    Verify that TrackingConfig instances are immutable.
    """
    cfg = TrackingConfig()
    with pytest.raises(ValidationError):
        cfg.max_dist_um = 30.0


def test_batch_config_defaults() -> None:
    """
    Verify default parameters of BatchConfig.
    """
    cfg = BatchConfig()
    assert cfg.workers == 16
    assert cfg.chunk_size == 10
    assert cfg.output_format == "parquet"
    assert cfg.ram_per_worker_gb == 1.2
    assert cfg.ram_cap_fraction == 0.6


def test_batch_config_custom_values() -> None:
    """
    Verify custom initialization of BatchConfig.
    """
    cfg = BatchConfig(
        workers=8,
        chunk_size=5,
        output_format="csv",
        ram_per_worker_gb=2.0,
        ram_cap_fraction=0.8,
    )
    assert cfg.workers == 8
    assert cfg.chunk_size == 5
    assert cfg.output_format == "csv"
    assert cfg.ram_per_worker_gb == 2.0
    assert cfg.ram_cap_fraction == 0.8


def test_batch_config_validation_errors() -> None:
    """
    Verify constraint validation on BatchConfig.
    """
    with pytest.raises(ValidationError):
        BatchConfig(workers=0)

    with pytest.raises(ValidationError):
        BatchConfig(chunk_size=0)

    with pytest.raises(ValidationError):
        BatchConfig(ram_per_worker_gb=0.0)

    with pytest.raises(ValidationError):
        BatchConfig(ram_cap_fraction=-0.1)

    with pytest.raises(ValidationError):
        BatchConfig(ram_cap_fraction=1.5)


def test_batch_config_frozen() -> None:
    """
    Verify that BatchConfig instances are immutable.
    """
    cfg = BatchConfig()
    with pytest.raises(ValidationError):
        cfg.workers = 4


def test_tracking_config_resolve_for_dt_without_dt_returns_self() -> None:
    cfg = TrackingConfig(max_dist_um=12.0, gap_dist_um=18.0, max_speed_um_s=100.0)
    resolved = cfg.resolve_for_dt(None)
    assert resolved is cfg


def test_tracking_config_resolve_for_dt_scales_from_max_speed() -> None:
    cfg = TrackingConfig(max_speed_um_s=100.0, min_len=4)
    resolved = cfg.resolve_for_dt(0.1)

    assert resolved.max_dist_um == pytest.approx(10.0)
    assert resolved.gap_dist_um == pytest.approx(12.5)
    assert resolved.min_len == 4
    assert resolved.max_speed_um_s == 100.0


def test_tracking_config_resolve_for_dt_explicit_overrides() -> None:
    cfg = TrackingConfig(max_speed_um_s=100.0)

    overridden_max = cfg.resolve_for_dt(0.1, explicit_max_dist=16.0)
    assert overridden_max.max_dist_um == pytest.approx(16.0)
    assert overridden_max.gap_dist_um == pytest.approx(20.0)

    overridden_both = cfg.resolve_for_dt(0.1, explicit_max_dist=16.0, explicit_gap_dist=30.0)
    assert overridden_both.max_dist_um == pytest.approx(16.0)
    assert overridden_both.gap_dist_um == pytest.approx(30.0)

    only_gap = cfg.resolve_for_dt(None, explicit_gap_dist=40.0)
    assert only_gap.max_dist_um == pytest.approx(20.0)
    assert only_gap.gap_dist_um == pytest.approx(40.0)


def test_tracking_config_resolve_for_dt_invalid_inputs() -> None:
    cfg = TrackingConfig()

    with pytest.raises(ValueError, match="dt_s must be positive"):
        cfg.resolve_for_dt(0.0)

    with pytest.raises(ValidationError):
        cfg.resolve_for_dt(0.1, explicit_max_dist=-1.0)

    with pytest.raises(ValidationError):
        cfg.resolve_for_dt(0.1, explicit_gap_dist=0.0)


@pytest.fixture
def region() -> RegionOfInterest:
    return RegionOfInterest(
        x_min=10.0,
        x_max=100.0,
        y_min=20.0,
        y_max=200.0,
        z_min=5.0,
        z_max=50.0,
    )


@pytest.fixture
def frame_range() -> FrameRange:
    return FrameRange(start=10, end=100)


@pytest.fixture
def roi_config() -> RoiConfig:
    return RoiConfig()


def test_default_values():
    config = RoiConfig()

    assert config.x_min is None
    assert config.x_max is None
    assert config.y_min is None
    assert config.y_max is None
    assert config.z_min is None
    assert config.z_max is None
    assert config.t0 is None
    assert config.t1 is None


def test_model_is_frozen(roi_config: RoiConfig):
    with pytest.raises(ValidationError):
        roi_config.x_min = 10.0


def test_with_region(
    roi_config: RoiConfig,
    region: RegionOfInterest,
):
    updated = roi_config.with_region(region)

    assert updated.x_min == region.x_min
    assert updated.x_max == region.x_max
    assert updated.y_min == region.y_min
    assert updated.y_max == region.y_max
    assert updated.z_min == region.z_min
    assert updated.z_max == region.z_max


def test_with_region_none_clears_spatial_bounds(
    region: RegionOfInterest,
):
    config = RoiConfig().with_region(region)

    updated = config.with_region(None)

    assert updated.x_min is None
    assert updated.x_max is None
    assert updated.y_min is None
    assert updated.y_max is None
    assert updated.z_min is None
    assert updated.z_max is None


def test_with_region_preserves_frame_range(
    frame_range: FrameRange,
    region: RegionOfInterest,
):
    config = RoiConfig().with_frame_range(frame_range)

    updated = config.with_region(region)

    assert updated.frame_range == frame_range


def test_with_region_does_not_modify_original(
    roi_config: RoiConfig,
    region: RegionOfInterest,
):
    updated = roi_config.with_region(region)

    assert updated is not roi_config
    assert roi_config.region is None
    assert updated.region == region


def test_with_frame_range(
    roi_config: RoiConfig,
    frame_range: FrameRange,
):
    updated = roi_config.with_frame_range(frame_range)

    assert updated.t0 == frame_range.start
    assert updated.t1 == frame_range.end


def test_with_frame_range_none_clears_temporal_bounds(
    frame_range: FrameRange,
):
    config = RoiConfig().with_frame_range(frame_range)

    updated = config.with_frame_range(None)

    assert updated.t0 is None
    assert updated.t1 is None


def test_with_frame_range_preserves_spatial_region(
    frame_range: FrameRange,
    region: RegionOfInterest,
):
    config = RoiConfig().with_region(region)

    updated = config.with_frame_range(frame_range)

    assert updated.region == region


def test_with_frame_range_does_not_modify_original(
    roi_config: RoiConfig,
    frame_range: FrameRange,
):
    updated = roi_config.with_frame_range(frame_range)

    assert updated is not roi_config
    assert roi_config.frame_range is None
    assert updated.frame_range == frame_range


def test_region_returns_none_when_bounds_are_unset(
    roi_config: RoiConfig,
):
    assert roi_config.region is None


@pytest.mark.parametrize(
    "missing_field",
    [
        "x_min",
        "x_max",
        "y_min",
        "y_max",
        "z_min",
        "z_max",
    ],
)
def test_region_returns_none_when_a_bound_is_missing(
    region: RegionOfInterest,
    missing_field: str,
):
    config = RoiConfig().with_region(region).model_copy(update={missing_field: None})

    assert config.region is None


def test_region_returns_region_of_interest(
    region: RegionOfInterest,
):
    config = RoiConfig().with_region(region)

    assert config.region == region
    assert isinstance(config.region, RegionOfInterest)


def test_frame_range_returns_none_when_bounds_are_unset(
    roi_config: RoiConfig,
) -> None:
    assert roi_config.frame_range is None


@pytest.mark.parametrize("missing_field", ["t0", "t1"])
def test_frame_range_returns_none_when_a_bound_is_missing(
    frame_range: FrameRange,
    missing_field: str,
):
    config = RoiConfig().with_frame_range(frame_range).model_copy(update={missing_field: None})

    assert config.frame_range is None


def test_frame_range_returns_frame_range(
    frame_range: FrameRange,
):
    config = RoiConfig().with_frame_range(frame_range)

    assert config.frame_range == frame_range
    assert isinstance(config.frame_range, FrameRange)
