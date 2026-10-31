from dataclasses import asdict, dataclass, fields


@dataclass
class RegionOfInterest:
    """Start-end coordinates of the region of interest (ROI) along each axis.

    If a coordinate is `None` the ROI is unbounded along that axis.
    """

    z0: int | None = None
    z1: int | None = None
    y0: int | None = None
    y1: int | None = None
    x0: int | None = None
    x1: int | None = None

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


def clamp(a: int | None, lo: int, hi: int) -> int:
    """Clamps optional integer within [lo, hi]"""

    return min(hi, max(lo, lo if a is None else int(a)))


def roi_slices(roi: RegionOfInterest, shape: tuple[int, int, int]) -> tuple[slice, slice, slice]:
    """Slices (z, y, x) of the ROI, bounds included."""

    def slice_from(start: int | None, end: int | None, n: int) -> slice:
        lo = clamp(start, 0, n - 1)
        hi = n - 1 if end is None else max(lo, min(int(end), n - 1))
        return slice(lo, hi + 1)

    z, y, x = shape
    return slice_from(roi.z0, roi.z1, z), slice_from(roi.y0, roi.y1, y), slice_from(roi.x0, roi.x1, x)


def roi_offset(roi: RegionOfInterest, shape: tuple[int, int, int]) -> tuple[int, int, int]:
    """Origin of the ROI in voxels (z, y, x)"""

    z, y, x = shape
    return clamp(roi.z0, 0, z - 1), clamp(roi.y0, 0, y - 1), clamp(roi.x0, 0, x - 1)
