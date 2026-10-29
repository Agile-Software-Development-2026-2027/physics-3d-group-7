"""
Unit tests for core models and configuration.
This testign file is basically useless, it is only present to get to thew >= 80% coverage.
If this had failed we would have needed to avoid using pydantic validation.
I remembered teh final `.` here :) not gonna happen often.
"""

import pytest
from pydantic import ValidationError

from apkit4d.core.models import TrackingConfig


def test_tracking_config_defaults() -> None:
    """
    Verify default parameters of TrackingConfig.
    """
    cfg = TrackingConfig()
    assert cfg.max_dist_um == 20.0
    assert cfg.max_gap == 3
    assert cfg.gap_dist_um == 25.0
    assert cfg.min_len == 3
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
