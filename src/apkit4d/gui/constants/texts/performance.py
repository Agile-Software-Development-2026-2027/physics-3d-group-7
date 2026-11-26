"""Texts of the performance settings dialog."""

PERFORMANCE_DIALOG_TITLE: str = "Performance Settings"

PERFORMANCE_LOADING_MODE: str = "Frame loading strategy"
PERFORMANCE_MODE_LAZY: str = "Lazy loading"
PERFORMANCE_MODE_AUTOMATIC: str = "Automatic preloading"
PERFORMANCE_MODE_MANUAL: str = "Manual cache limit"
PERFORMANCE_MODE_FULL: str = "Full dataset preloading"

PERFORMANCE_LOOKAHEAD: str = "Lookahead duration (s)"
PERFORMANCE_CACHE_LIMIT: str = "Cache limit (GB)"
PERFORMANCE_MEMORY_RESERVE: str = "Memory reserve (%)"

PERFORMANCE_DESCRIPTION_LAZY: str = "Load frames only when requested, minimizing memory usage."

PERFORMANCE_DESCRIPTION_AUTOMATIC: str = (
    "Preload upcoming frames based on playback speed and available system memory."
)

PERFORMANCE_DESCRIPTION_MANUAL: str = "Preload upcoming frames within a user-defined cache size limit."

PERFORMANCE_DESCRIPTION_FULL: str = "Preload the entire dataset into RAM if sufficient memory is available."

PERFORMANCE_TOOLTIP_LOOKAHEAD: str = "Duration of upcoming playback to preload in seconds."

PERFORMANCE_TOOLTIP_CACHE_LIMIT: str = "Maximum amount of RAM that the frame cache may use."

PERFORMANCE_TOOLTIP_MEMORY_RESERVE: str = (
    "Percentage of total system memory to keep available for other operations."
)
