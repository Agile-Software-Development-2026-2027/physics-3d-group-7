from dataclasses import dataclass, field
from typing import Any, Self


@dataclass(frozen=True)
class FrameRange:
    """An immutable, inclusive range of frame indices.

    The range is zero-based. The start index is clamped to the end index
    whenever the bounds are inconsistent.
    """

    START = "t0"
    END = "t1"

    start: int = field()
    end: int = field()

    def __post_init__(self):
        clamped_start = max(0, min(self.start, self.end))
        clamped_end = max(0, self.end)

        object.__setattr__(self, "start", clamped_start)
        object.__setattr__(self, "end", clamped_end)

    @classmethod
    def full(cls, n_frames: int) -> Self:
        """Create a range covering all available frames.

        Ensures at least one frame is included, even if n_frames is zero
        or negative.
        """

        return cls(0, max(n_frames, 1) - 1)

    @classmethod
    def from_dict(cls, params: dict[str, Any]) -> Self | None:
        """Create a frame range from a dictionary.

        Returns None if either boundary is missing.
        """

        first, last = params.get(cls.START), params.get(cls.END)

        if first is None or last is None:
            return None

        return cls(int(first), int(last))

    @property
    def start_display(self) -> int:
        """Return the start index using one-based indexing."""

        return self.start + 1

    @property
    def end_display(self) -> int:
        """Return the end index using one-based indexing."""

        return self.end + 1

    @property
    def count(self) -> int:
        """Return the number of frames included in the range."""

        return self.end - self.start + 1

    def to_dict(self) -> dict[str, int]:
        """Convert the frame range to a dictionary."""

        return {self.START: self.start, self.END: self.end}

    def with_start(self, start: int) -> Self:
        """Return a copy with an updated start boundary.

        If start exceeds the current end, it is clamped to the end.

        Args:
            start: start frame (0-based)
        """

        return type(self)(max(0, min(start, self.end)), self.end)

    def with_end(self, end: int) -> Self:
        """Return a copy with an updated end boundary.

        If end is before the current start, it is clamped to the start.

        Args:
            end: end frame (0-based)
        """

        return type(self)(self.start, max(0, max(end, self.start)))

    def contains(self, other: FrameRange) -> bool:
        """Return True if every frame of `other` is also a frame of this range."""

        return (other.start >= self.start and other.start <= self.end) and (
            other.end <= self.end and other.end >= self.start
        )

    def clamp(self, other: FrameRange) -> Self:
        """Return a copy of this range moved inside `other`.

        Each end is clamped independently into `other`, so an end that is already inside
        `other` is left where it is. The result is always a valid range (start <= end)
        contained in `other`. A range entirely outside `other` collapses onto the single
        frame of `other` nearest to it.

        Args:
            other: The range the result must be contained in.

        Returns:
            A new range with `other.start <= start <= end <= other.end`.
        """
        return type(self)(
            min(max(self.start, other.start), other.end),
            min(max(self.end, other.start), other.end),
        )
