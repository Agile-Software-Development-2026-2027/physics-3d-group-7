"""
Data models and configurations for apkit4d tracking and batching pipeline.
"""

from typing import ClassVar, Self

from pydantic import BaseModel, ConfigDict, Field

from apkit4d.tracking.motion import compute_search_gate


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
        default=5,
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

    def resolve_for_dt(
        self,
        dt_s: float | None,
        explicit_max_dist: float | None = None,
        explicit_gap_dist: float | None = None,
    ) -> Self:
        """Resolve search gate radii from frame interval `dt_s` and `max_speed_um_s`.

        `explicit_max_dist` takes precedence over `max_speed_um_s * dt_s`. When
        `explicit_gap_dist` is omitted and either `explicit_max_dist` or `dt_s` is
        provided, `gap_dist_um` defaults to `1.25 * resolved_max_dist`.
        """
        if explicit_max_dist is not None:
            resolved_max_dist = float(explicit_max_dist)
        elif dt_s is not None:
            resolved_max_dist = compute_search_gate(dt_s, self.max_speed_um_s)
        else:
            resolved_max_dist = self.max_dist_um

        if explicit_gap_dist is not None:
            resolved_gap_dist = float(explicit_gap_dist)
        elif explicit_max_dist is not None or dt_s is not None:
            resolved_gap_dist = 1.25 * resolved_max_dist
        else:
            resolved_gap_dist = self.gap_dist_um

        if resolved_max_dist == self.max_dist_um and resolved_gap_dist == self.gap_dist_um:
            return self

        return type(self).model_validate(
            {
                **self.model_dump(),
                "max_dist_um": resolved_max_dist,
                "gap_dist_um": resolved_gap_dist,
            }
        )


class BatchConfig(BaseModel):
    """Configuration parameters for batch blob detection across frames.

    Attributes:
        workers: Number of parallel worker processes.
        chunk_size: Number of frames assigned to each worker task chunk.
        output_format: Storage table format ('parquet' or 'csv').
        ram_per_worker_gb: Estimated RAM per worker in gigabytes for memory capping.
        ram_cap_fraction: Maximum fraction of available RAM allowed for workers.

    RefactorNote:
        Pydantic BaseModel configuration following the TrackingConfig architecture.
        Replaces hardcoded worker counts and chunk sizes from legacy `batch.py`.
        Frozen model ensures immutable settings during batch execution.
    """

    model_config = ConfigDict(frozen=True)

    workers: int = Field(
        default=16,
        ge=1,
        description="Number of parallel worker processes to use.",
    )
    chunk_size: int = Field(
        default=10,
        ge=1,
        description="Number of frames assigned to each worker task chunk.",
    )
    output_format: str = Field(
        default="parquet",
        description="Format of the output table ('parquet' or 'csv').",
    )
    ram_per_worker_gb: float = Field(
        default=1.2,
        gt=0.0,
        description="Estimated RAM consumption per worker in gigabytes.",
    )
    ram_cap_fraction: float = Field(
        default=0.6,
        gt=0.0,
        le=1.0,
        description="Fraction of available system RAM allowed for worker processes.",
    )


class DetectionConfig(BaseModel):
    """Configuration for blob detection.

    Attributes:
        LOG_THRESHOLD_MIN: Minimum allowed value for the LoG threshold
        LOG_THRESHOLD_MAX: Maximum allowed value for the LoG threshold
        diameter_xy_um: Expected blob size for the LoG filter scale along the X and Y axes.
                        Affects how far apart detected seeds must be.
        diameter_z_um: Expected blob size for the LoG filter scale along the Z axis.
                       Usually elongated w.r.t. the X and Y axes.
        threshold: -LoG response threshold over the preprocessed volume in [0, 1]
        split: Minimum tolerated distance between the seeds, expressed as a fraction
               of the diameter. Below 1.0 the cell breaks down in more cells in the
               direction of Z. (misurato sul file LF4D 10x: a 0.6 il 32% dei blob ha un
               vicino a meno di 8 µm in XY, a 1.0 il 5%)
        grow_frac: Boundary of a segmented (via watershedding) region, expressed as a fraction of the peak.
        min_volume_um3: Min volume of a blob. Blobs with volume under this constraint are filtered out.
        max_volume_um3: Max volume of a blob. Blobs with volume above this constraint are filtered out.
    """

    model_config = ConfigDict(frozen=True)

    LOG_THRESHOLD_MIN: ClassVar[float] = 0.0
    LOG_THRESHOLD_MAX: ClassVar[float] = 5.0

    diameter_xy_um: float = Field(
        default=15.0,
        ge=1.0,
        description="""
        Expected blob size for the LoG filter scale along the X and Y axes.
        Affects how far apart detected seeds must be.
        """.replace("\n", ""),
    )
    diameter_z_um: float = Field(
        default=70.0,
        ge=1.0,
        description="""
        Expected blob size for the LoG filter scale along the Z axis.
        Usually elongated w.r.t. the X and Y axes.
        """.replace("\n", ""),
    )

    threshold: float = Field(
        default=0.1,
        ge=LOG_THRESHOLD_MIN,
        le=LOG_THRESHOLD_MAX,
        description="-LoG response threshold over the preprocessed volume in [0, 1]",
    )

    split: float = Field(
        default=1.0,
        ge=0.1,
        description="""
        Minimum tolerated distance between the seeds, expressed as a fraction of the diameter.
        Below 1.0 the cell breaks down in more cells in the direction of Z.
        """.replace("\n", ""),
    )

    grow_frac: float = Field(
        default=0.3,
        ge=0.01,
        description="Boundary of a segmented (via watershedding) region, expressed as a fraction of the peak",
    )

    min_volume_um3: float = Field(
        default=200.0,
        ge=0.0,
        description="Min volume of a blob. Blobs with volume under this constraint are filtered out.",
    )

    max_volume_um3: float = Field(
        default=1e6,
        ge=0.0,
        description="Min volume of a blob. Blobs with volume under this constraint are filtered out.",
    )
