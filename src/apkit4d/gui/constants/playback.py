"""
Timing and limits of the playback.
"""

DEFAULT_SPEED_FPS: float = 10.0  # frames per second, as fast as the playback always was
MIN_SPEED_FPS: float = 0.1
MAX_SPEED_FPS: float = 240.0
SPEED_STEP_FPS: float = 1.0  # how much the speed changes with the buttons of the speed field
SPEED_DECIMALS: int = 1

DEFAULT_STEP: int = 1  # frames that the playback and the buttons skip at every move
MIN_STEP: int = 1
