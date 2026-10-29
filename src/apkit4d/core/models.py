"""
Data models and configurations for apkit4d tracking pipeline.
"""

from pydantic import BaseModel, ConfigDict, Field


class TrackingConfig(BaseModel):
    """Configuration parameters for particle tracking and trajectory linking.

    Attributes:
        max_dist_um: Search gate radius for frame-to-frame linking (in micrometers).
        max_gap: Maximum number of missing frames bridgeable during gap closing.
        gap_dist_um: Search radius per gap frame during gap closing (in micrometers).
        min_len: Minimum number of detection points required to retain a trajectory.
        velocity_smoothing: Weight of newly observed velocity in EMA update (0.0 = static).
        mc_resamples: Number of Monte Carlo resamples for connection stability (0 = disable).
        max_speed_um_s: Expected maximum physical velocity of particles (in micrometers/second).

    RefactorNote:
        This class if a refactor based on LinkParams from legacy
        Instead of using a dataclass, we use pydantic BaseModel for validation and serialization since
        why should we reinvent the wheel???
        Also the name was changed because parameters are a specific thing they arte not meant to be used
        for data structures the name was confusing
        All the termninology was migrated to english anddatatypes in comments follow tehir definition
        we basically do not use 0 to indicate a float (we use 0.0).
        The names of some variables, liek vel_smooth, was extended (velocity_smoothing) we assume in
        programming taht the less a filed is used the longer it's name should be more expressive.
        For some reasons everything but max_speed_um_s was inlcuded in the original implementation
        sincewe want to have as much as possible a single source of truth we included it here
        We chose to have them frozen because we do not want to have a situation where the parameters
        change in the middle of tracking, changing them this way requires recreating the object

    Note:
        max_speed_um_s is capped at 250.0, if it becomes a problem we can increment it but the original
        code seems to avoid going overe 250.0 so we will keep it as is for now.
    """

    model_config = ConfigDict(frozen=True)

    max_dist_um: float = Field(
        default=20.0,
        gt=0.0,
        description="Search gate radius for frame-to-frame linking in micrometers.",
    )
    max_gap: int = Field(
        default=3,
        ge=0,
        description="Maximum number of missing frames bridgeable during gap closing.",
    )
    gap_dist_um: float = Field(
        default=25.0,
        gt=0.0,
        description="Search radius per gap frame during gap closing in micrometers.",
    )
    min_len: int = Field(
        default=3,
        ge=2,
        description="Minimum number of detection points required to retain a trajectory.",
    )
    velocity_smoothing: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Exponential moving average velocity update weight in [0, 1].",
    )
    mc_resamples: int = Field(
        default=20,
        ge=0,
        description="Monte Carlo resamples for link stability estimation (0 to disable).",
    )
    max_speed_um_s: float = Field(
        default=250.0,
        gt=0.0,
        description="Maximum expected physical swimming speed in micrometers/second.",
    )
