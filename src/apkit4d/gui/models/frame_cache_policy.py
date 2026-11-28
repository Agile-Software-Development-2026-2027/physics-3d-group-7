"""Memory management policy for the frame cache."""

import psutil

from apkit4d.gui.models.frame_loading_config import (
    FrameLoadingConfig,
    FrameLoadingMode,
)

BYTES_PER_GB = 1000**3


def calculate_cache_limit(
    config: FrameLoadingConfig,
    cached_bytes: int,
    initial_available_bytes: int,
) -> int:
    """Calculate a cache limit based on configuration and available RAM."""
    if config.mode == FrameLoadingMode.LAZY:
        return 0
    memory = psutil.virtual_memory()
    reserve_bytes = memory.total * config.memory_reserve_percent // 100
    initial_budget = max(
        0,
        initial_available_bytes - reserve_bytes,
    )
    available_budget = max(
        0,
        memory.available + cached_bytes - reserve_bytes,
    )
    limit = min(initial_budget, available_budget)
    if config.mode == FrameLoadingMode.MANUAL:
        limit = min(
            limit,
            int(config.cache_limit_gb * BYTES_PER_GB),
        )
    return limit
