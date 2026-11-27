"""Tests for frame loading configuration."""

import pytest
from pydantic import ValidationError

from apkit4d.gui.models.frame_loading_config import (
    FrameLoadingConfig,
    FrameLoadingMode,
)


def test_default_config() -> None:
    config = FrameLoadingConfig()

    assert config.mode == FrameLoadingMode.AUTOMATIC
    assert config.lookahead_seconds == 2.0
    assert config.cache_limit_gb == 8.0
    assert config.memory_reserve_percent == 20


@pytest.mark.parametrize("mode", list(FrameLoadingMode))
def test_loading_modes(mode: FrameLoadingMode) -> None:
    config = FrameLoadingConfig(mode=mode)

    assert config.mode == mode


@pytest.mark.parametrize(
    "values",
    [
        {"mode": "invalid"},
        {"lookahead_seconds": 0},
        {"lookahead_seconds": -1},
        {"lookahead_seconds": float("inf")},
        {"cache_limit_gb": 0},
        {"cache_limit_gb": -1},
        {"cache_limit_gb": float("inf")},
        {"memory_reserve_percent": 0},
        {"memory_reserve_percent": 100},
    ],
)
def test_invalid_config(values: dict) -> None:
    with pytest.raises(ValidationError):
        FrameLoadingConfig(**values)
