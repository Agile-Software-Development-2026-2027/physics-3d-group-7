"""
this module defines the RegionOfInterest class, which represents a 3D Region of Interest

it is saved in world coordinates so that it can be created either by clicking with the mouse
in the 3D Viewport or by entering the coordinates from the keyboard in a text field

when we need to crop the 3D NumPy matrix, micrometers are converted to voxel indices

IMPORTANT!!!!!!!!!!!!!! I NEED TO NOW IF IT IS GOOD FOR YOU THE WORKFLOW I AM THINKING

the workflow is something like this:
in viewport the user clicks and drags so we have 2 points, viewport calculates view direction
and then calls RegionOfInterest.from_points(), this func will expand the ROI to the full dept
viewport now has the bounds to display the ROI box
now the user wants to modify the ROI by dragging the bounds with some handles,
viewport will call RegionOfInterest.from_bounds() to create a new ROI, clamped to the volume bounds
then the user click some button to accept
now the volume controller reads the final roi and extracts the subvolume with
RegionOfInterest.extract_subvolume()
and then passes the cropped volume to create_volume_grid()
to create a new grid with the new origin and voxel size
same thing for the blobs
"""

import math
from dataclasses import asdict, dataclass, fields
from typing import Self

import numpy as np
import pandas as pd

type Bounds6D = tuple[float, float, float, float, float, float]
type Point3D = tuple[float, float, float] | np.ndarray
type Shape3D = tuple[int, int, int]
type VoxelSize3D = tuple[float, float, float]
type Origin3D = tuple[float, float, float]


@dataclass(frozen=True)
class RegionOfInterest:
    """
    this class represents a 3D Region of Interest (ROI) in world coordinates

    the attributes follow the standard order of PyVista/VTK: X, Y, Z.

    """

    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def __post_init__(self) -> None:
        # check that the ROI is valid: min cannot exceed max for any axis
        if self.x_min > self.x_max or self.y_min > self.y_max or self.z_min > self.z_max:
            raise ValueError(
                f"Coordinate ROI non valide: i minimi non possono superare i massimi "
                f"(X=[{self.x_min}, {self.x_max}], Y=[{self.y_min}, {self.y_max}], "
                f"Z=[{self.z_min}, {self.z_max}])."
            )

    # something used by worker.py to convert the ROI to a dictionary for serialization
    def to_dict(self):
        return asdict(self)

    # something used by worker.py to convert a dictionary back to a RegionOfInterest instance
    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})

    @property
    def bounds(self) -> Bounds6D:
        # returns the 6D bounds of the ROI in world coordinates (micrometers)
        return (self.x_min, self.x_max, self.y_min, self.y_max, self.z_min, self.z_max)

    @property
    def size_xyz(self) -> tuple[float, float, float]:
        # returns the size of the ROI along each axis (X, Y, Z) in micrometers
        return (self.x_max - self.x_min, self.y_max - self.y_min, self.z_max - self.z_min)

    @property
    def origin_xyz(self) -> Origin3D:
        # returns the physical origin (x_min, y_min, z_min) in micrometers
        return (self.x_min, self.y_min, self.z_min)

    @classmethod
    def from_bounds(
        cls,
        bounds: Bounds6D,
        volume_bounds: Bounds6D | None = None,
        min_size: float = 1e-3,
    ) -> Self:
        """
        creates a valid RegionOfInterest from 6 coordinates (from mouse or text fields).
        automatically reorders min/max, clamps the ROI inside `volume_bounds` (if provided)
        and ensures a minimum thickness `min_size` to avoid flat 2D boxes.

        Parameters:
            - bounds: 6D tuple (x0, x1, y0, y1, z0, z1) in micrometers
            - volume_bounds: optional 6D tuple (vx0, vx1, vy0, vy1, vz0, vz1)
            in micrometers to clamp the ROI inside
            - min_size: minimum thickness in micrometers for each axis (default 1e-3)

        Returns:
            - RegionOfInterest instance with valid coordinates

        """
        x0, x1 = float(min(bounds[0], bounds[1])), float(max(bounds[0], bounds[1]))
        y0, y1 = float(min(bounds[2], bounds[3])), float(max(bounds[2], bounds[3]))
        z0, z1 = float(min(bounds[4], bounds[5])), float(max(bounds[4], bounds[5]))

        if volume_bounds is not None:
            # clamp the ROI inside the volume bounds and ensure a minimum size
            vx0, vx1 = min(volume_bounds[0], volume_bounds[1]), max(volume_bounds[0], volume_bounds[1])
            vy0, vy1 = min(volume_bounds[2], volume_bounds[3]), max(volume_bounds[2], volume_bounds[3])
            vz0, vz1 = min(volume_bounds[4], volume_bounds[5]), max(volume_bounds[4], volume_bounds[5])

            x0, x1 = _clamp_and_ensure_span(x0, x1, vx0, vx1, min_size)
            y0, y1 = _clamp_and_ensure_span(y0, y1, vy0, vy1, min_size)
            z0, z1 = _clamp_and_ensure_span(z0, z1, vz0, vz1, min_size)
        else:
            # if no volume bounds are provided, we still ensure a minimum size for the ROI
            if x1 - x0 < min_size:
                x1 = x0 + min_size
            if y1 - y0 < min_size:
                y1 = y0 + min_size
            if z1 - z0 < min_size:
                z1 = z0 + min_size

        # return a new RegionOfInterest instance with the validated and adjusted coordinates
        return cls(x_min=x0, x_max=x1, y_min=y0, y_max=y1, z_min=z0, z_max=z1)

    @classmethod
    def from_points(
        cls,
        point_a: Point3D,
        point_b: Point3D,
        volume_bounds: Bounds6D | None = None,
        view_direction: Point3D | None = None,
        min_size: float = 1e-3,
    ) -> Self:
        """
        Creates a RegionOfInterest from two 3D points (point_a and point_b).
        it calls `from_bounds()` internally to ensure the ROI is valid, clamped,
        and has a minimum size.

        if `volume_bounds` is provided:
        - if `view_direction` (the camera's view direction) is provided, the axis
            most aligned with the view is automatically extended to the full depth of the volume
            when P1 and P2 lie on the same face (or have thickness < min_size on that axis).
        - if `view_direction` is not provided but one of the axes has thickness < min_size
            (e.g., the two points were clicked on the same Z face), that axis is extended to the
            full thickness of `volume_bounds`.


        Parameters:
            - point_a: first 3D point (x, y, z)
            - point_b: second 3D point (x, y, z)
            - volume_bounds: optional 6D tuple (vx0, vx1, vy0, vy1, vz0, vz1)
            in micrometers to clamp the ROI inside
            - view_direction: optional 3D vector (vx, vy, vz) representing the camera's view direction
            - min_size: minimum thickness in micrometers for each axis (default 1e-3)

        Returns:
            - RegionOfInterest instance with valid coordinates
        """
        x0, x1 = float(min(point_a[0], point_b[0])), float(max(point_a[0], point_b[0]))
        y0, y1 = float(min(point_a[1], point_b[1])), float(max(point_a[1], point_b[1]))
        z0, z1 = float(min(point_a[2], point_b[2])), float(max(point_a[2], point_b[2]))

        if volume_bounds is not None:
            vx0, vx1 = min(volume_bounds[0], volume_bounds[1]), max(volume_bounds[0], volume_bounds[1])
            vy0, vy1 = min(volume_bounds[2], volume_bounds[3]), max(volume_bounds[2], volume_bounds[3])
            vz0, vz1 = min(volume_bounds[4], volume_bounds[5]), max(volume_bounds[4], volume_bounds[5])

            if view_direction is not None:
                # find the axis most aligned with the view direction and extend it to the
                # full depth of the volume
                vd = np.abs(np.asarray(view_direction, dtype=np.float64))
                depth_axis = int(np.argmax(vd))
                if depth_axis == 0:
                    x0, x1 = vx0, vx1
                elif depth_axis == 1:
                    y0, y1 = vy0, vy1
                else:
                    z0, z1 = vz0, vz1
            else:
                # if no view_direction is provided, we extend any flat axis (thickness < min_size)
                # when at least one of the other axes has been dragged

                spans = (x1 - x0, y1 - y0, z1 - z0)
                if max(spans) >= min_size:
                    if spans[0] < min_size:
                        x0, x1 = vx0, vx1
                    if spans[1] < min_size:
                        y0, y1 = vy0, vy1
                    if spans[2] < min_size:
                        z0, z1 = vz0, vz1

        raw_bounds: Bounds6D = (x0, x1, y0, y1, z0, z1)
        return cls.from_bounds(raw_bounds, volume_bounds=volume_bounds, min_size=min_size)

    def to_voxel_slices(
        self,
        volume_shape: Shape3D,
        voxel_size: VoxelSize3D,
        origin_xyz: Origin3D = (0.0, 0.0, 0.0),
    ) -> tuple[tuple[slice, slice, slice], Origin3D]:
        """
        converts the ROI coordinates in micrometers to integer indices (slices)
        to crop the NumPy array (which has order Z, Y, X).

        Parameters:
            - volume_shape: shape of the 3D NumPy array (Z, Y, X)
            - voxel_size: size of each voxel in micrometers (sz, sy, sx)
            - origin_xyz: physical origin of the volume in micrometers (ox, oy, oz)

        Returns:
            - (z_slice, y_slice, x_slice): the 3 slices to use on "volume[z_slice, y_slice, x_slice]"
            - sub_origin_xyz: the new origin (ox, oy, oz) in micrometers of the cropped volume,
              to be passed as the `offset` parameter to "create_volume_grid()".
        """

        nz, ny, nx = volume_shape
        sz, sy, sx = voxel_size
        if nz <= 0 or ny <= 0 or nx <= 0:
            raise ValueError(f"volume_shape must have positive dimensions, received {volume_shape}.")
        if sz <= 0 or sy <= 0 or sx <= 0:
            raise ValueError(f"voxel_size must have positive values, received {voxel_size}.")

        ox, oy, oz = origin_xyz

        # convert the ROI coordinates in micrometers to voxel indices (Z, Y, X)
        ix_min, ix_max = _world_to_index_pair(self.x_min, self.x_max, ox, sx, nx)
        iy_min, iy_max = _world_to_index_pair(self.y_min, self.y_max, oy, sy, ny)
        iz_min, iz_max = _world_to_index_pair(self.z_min, self.z_max, oz, sz, nz)

        # we have to add +1 to the max indices because Python slicing is exclusive at the end
        slices = (
            slice(iz_min, iz_max + 1),
            slice(iy_min, iy_max + 1),
            slice(ix_min, ix_max + 1),
        )

        # calculate the new origin of the cropped volume in micrometers
        sub_origin_xyz: Origin3D = (
            float(ox + ix_min * sx),
            float(oy + iy_min * sy),
            float(oz + iz_min * sz),
        )
        return slices, sub_origin_xyz

    def extract_subvolume(
        self,
        volume: np.ndarray,
        voxel_size: VoxelSize3D,
        origin_xyz: Origin3D = (0.0, 0.0, 0.0),
    ) -> tuple[np.ndarray, Origin3D]:
        """
        this method extracts the subvolume of the 3D NumPy array that corresponds to the ROI.
        it returns the cropped volume and the new origin in micrometers of the subvolume by
        calling `to_voxel_slices()` internally.

        Parameters:
            - volume: 3D NumPy array (Z, Y, X)
            - voxel_size: size of each voxel in micrometers (sz, sy, sx)
            - origin_xyz: physical origin of the volume in micrometers (ox, oy, oz)

        Returns:
            - subvolume: the cropped 3D NumPy array corresponding to the ROI
            - sub_origin_xyz: the new origin (ox, oy, oz) in micrometers of the cropped volume,
            to be passed as the `offset` parameter to "create_volume_grid
        """
        if volume.ndim != 3:
            raise ValueError(f"volume must be 3D (Z, Y, X), received shape {volume.shape}.")
        shape: Shape3D = (int(volume.shape[0]), int(volume.shape[1]), int(volume.shape[2]))
        slices, sub_origin = self.to_voxel_slices(shape, voxel_size, origin_xyz)
        return volume[slices], sub_origin

    def filter_blobs_df(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        filters a DataFrame of blobs (with columns 'x_um', 'y_um', 'z_um') to keep only those
        that are inside the ROI. Returns a new DataFrame with the filtered blobs.

        Parameters:
            - df: DataFrame with columns 'x_um', 'y_um', 'z_um' representing the blob coordinates
            in micrometers

        Returns:
            - filtered_df: new DataFrame containing only the blobs inside the ROI
        """
        if df is None or df.empty:
            return pd.DataFrame() if df is None else df.copy()

        # here we create a boolean mask that checks if each blob's coordinates are within the ROI bounds
        mask = (
            (df["x_um"] >= self.x_min)
            & (df["x_um"] <= self.x_max)
            & (df["y_um"] >= self.y_min)
            & (df["y_um"] <= self.y_max)
            & (df["z_um"] >= self.z_min)
            & (df["z_um"] <= self.z_max)
        )
        # df.loc[mask] returns a view of the original DataFrame, so we call .copy() to return
        # a new DataFrame by passing mask to df.loc[], we select only the rows where the mask is True
        # that is, the blobs inside the ROI
        return df.loc[mask].copy()


def _clamp_and_ensure_span(
    val_min: float,
    val_max: float,
    bound_min: float,
    bound_max: float,
    min_size: float,
) -> tuple[float, float]:
    """
    function helper: clamps [val_min, val_max] within the limits of the volume [bound_min, bound_max]
    and ensures that the thickness is never zero.

    Parameters:
        - val_min: minimum value of the ROI along an axis
        - val_max: maximum value of the ROI along an axis
        - bound_min: minimum value of the volume along the same axis
        - bound_max: maximum value of the volume along the same axis
        - min_size: minimum thickness of the ROI along the axis

    Returns:
        - (clamped_min, clamped_max): the clamped and adjusted min/max values
    """
    c_min = max(bound_min, min(val_min, bound_max))
    c_max = max(bound_min, min(val_max, bound_max))

    span = min(min_size, bound_max - bound_min)
    if c_max - c_min < span:
        if c_min + span <= bound_max:
            c_max = c_min + span
        else:
            c_min = max(bound_min, c_max - span)

    return float(c_min), float(c_max)


def _world_to_index_pair(
    w_min: float,
    w_max: float,
    origin: float,
    spacing: float,
    axis_size: int,
) -> tuple[int, int]:
    """
    function helper: converts a physical range [w_min, w_max] in micrometers
    to a pair of integer voxel indices [idx_min, idx_max] between 0 and axis_size - 1.
    Ensures at least 2 points (1 VTK cell) when axis_size >= 2.

    Parameters:
        - w_min: minimum world coordinate in micrometers
        - w_max: maximum world coordinate in micrometers
        - origin: physical origin of the volume in micrometers
        - spacing: size of each voxel in micrometers
        - axis_size: number of voxels along the axis

    Returns:
        - (idx_min, idx_max): the corresponding voxel indices clamped to [0, axis_size - 1]
    """
    # i use round() to avoid floating point precision issues when converting to voxel indices
    raw_min = math.floor(round((w_min - origin) / spacing, 6))
    raw_max = math.ceil(round((w_max - origin) / spacing, 6))

    max_valid = axis_size - 1
    idx_min = max(0, min(raw_min, max_valid))
    idx_max = max(0, min(raw_max, max_valid))

    if idx_min == idx_max and axis_size >= 2:
        if idx_max < max_valid:
            idx_max += 1
        else:
            idx_min -= 1

    return idx_min, idx_max
