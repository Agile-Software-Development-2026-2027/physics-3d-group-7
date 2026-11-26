"""
Choices for the look of the 3D view that the left panel offers to the user.
"""

# colormaps the user can choose, as matplotlib names. The first one is used until the user changes it
COLORMAPS: tuple[str, ...] = ("inferno", "turbo", "viridis", "magma", "plasma", "cividis", "gray")

# opacity of the volume, in percent: 100 is the default look, 200 is twice as opaque
OPACITY_MIN_PERCENT: int = 10
OPACITY_MAX_PERCENT: int = 400
OPACITY_DEFAULT_PERCENT: int = 100

# trajectory visualization defaults
TRAJECTORY_COLORMAPS: tuple[str, ...] = ("inferno", "turbo", "viridis", "magma", "plasma", "cividis", "gray")
TRAJECTORY_TAIL_MIN: int = -1
TRAJECTORY_TAIL_MAX: int = 5000
TRAJECTORY_TAIL_DEFAULT: int = -1
TRAJECTORY_LINE_WIDTH_DEFAULT: float = 2.5

# visualization Sub-ROI outside opacity, in percent (default 1% = 0.01)
VIS_SUB_ROI_OPACITY_MIN_PERCENT: int = 0
VIS_SUB_ROI_OPACITY_MAX_PERCENT: int = 100
VIS_SUB_ROI_OPACITY_DEFAULT_PERCENT: int = 1
