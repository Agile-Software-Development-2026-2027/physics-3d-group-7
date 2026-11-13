"""
Choices for the look of the 3D view that the left panel offers to the user.
"""

# colormaps the user can choose, as matplotlib names. The first one is used until the user changes it
COLORMAPS: tuple[str, ...] = ("inferno", "viridis", "magma", "plasma", "cividis", "gray")

# opacity of the volume, in percent: 100 is the default look, 200 is twice as opaque
OPACITY_MIN_PERCENT: int = 10
OPACITY_MAX_PERCENT: int = 400
OPACITY_DEFAULT_PERCENT: int = 100
