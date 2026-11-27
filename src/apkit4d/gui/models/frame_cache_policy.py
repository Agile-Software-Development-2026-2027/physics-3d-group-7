
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
) -> int:
    """Calculate the cache limit based on configuration and available RAM."""
    if config.mode == FrameLoadingMode.LAZY:
        return 0

    memory = psutil.virtual_memory()

    reserve_bytes = (
        memory.total * config.memory_reserve_percent // 100
    )

    available_budget = max(
        0,
        memory.available + cached_bytes - reserve_bytes,
    )

    if config.mode == FrameLoadingMode.MANUAL:
        return int(
            min(
                available_budget,
                config.cache_limit_gb * BYTES_PER_GB,
            )
        )

    return available_budget
