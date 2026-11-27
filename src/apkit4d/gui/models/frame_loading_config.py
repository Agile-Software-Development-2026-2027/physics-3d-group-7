"""Configuration of frame loading strategies."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class FrameLoadingMode(StrEnum):
    """Available frame loading strategies."""

    LAZY = "lazy"
    AUTOMATIC = "automatic"
    MANUAL = "manual"
    FULL = "full"


class FrameLoadingConfig(BaseModel):
    """Configuration parameters for frame loading and memory management."""

    model_config = ConfigDict(frozen=True)

    mode: FrameLoadingMode = FrameLoadingMode.AUTOMATIC

    lookahead_seconds: float = Field(
        default=2.0,
        gt=0.0,
        allow_inf_nan=False,
        description="Duration of playback to preload in seconds.",
    )
    cache_limit_gb: float = Field(
        default=8.0,
        gt=0.0,
        allow_inf_nan=False,
        description="Maximum cache size in gigabytes.",
    )
    memory_reserve_percent: int = Field(
        default=20,
        ge=1,
        lt=100,
        description="Percentage of total system memory to keep available.",
    )
