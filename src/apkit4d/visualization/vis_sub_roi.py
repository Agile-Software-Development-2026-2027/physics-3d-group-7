"""Pure state and spatial geometry helpers for the Visualization Sub-ROI feature.

This module operates strictly in world coordinates (micrometers) for visualization-only
attenuation and never mutates source volumes, blob tables, or 'PreparedTrajectories'.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pyvista as pv
from numpy.typing import NDArray

from apkit4d.core.roi import Bounds6D, _clamp_bounds_6d, _normalize_bounds
from apkit4d.visualization.data_mapper import (
    PreparedTrajectories,
    TrajectoryRenderConfig,
    build_trajectory_polydata,
)

DEFAULT_OUTSIDE_OPACITY: float = 0.01
_MIN_AXIS_SPAN: float = 1e-12


def clamp_outside_opacity(opacity: float) -> float:
    """Clamp an opacity factor into [0.0, 1.0], rejecting NaN/infinite values."""
    val = float(opacity)
    if not math.isfinite(val):
        raise ValueError(f"outside_opacity must be finite, received {opacity!r}.")
    return float(np.clip(val, 0.0, 1.0))


def outside_opacity_to_alpha_uint8(outside_opacity: float) -> int:
    """Convert an outside opacity factor in [0.0, 1.0] to a 'uint8' alpha channel value."""
    clamped = clamp_outside_opacity(outside_opacity)
    return int(np.clip(round(clamped * 255.0), 0, 255))


@dataclass(frozen=True)
class VisSubRoiState:
    """Shared visualization-only state to make volume, blobs, and tracks outside a box
    less visible.

    Attributes:
        enabled: Whether spatial outside opacity attenuation is currently active.
        bounds: World-space "(x_min, x_max, y_min, y_max, z_min, z_max)" in micrometers,
            or 'None' when no Sub-ROI box has been defined.
        outside_opacity: Opacity multiplier in [0.0, 1.0] applied outside 'bounds'
            when 'enabled' is 'True' (default '0.01' = 1%).
    """

    enabled: bool = False
    bounds: Bounds6D | None = None
    outside_opacity: float = DEFAULT_OUTSIDE_OPACITY

    # post-init validation and normalization of 'bounds' and 'outside_opacity'
    def __post_init__(self) -> None:
        object.__setattr__(self, "outside_opacity", clamp_outside_opacity(self.outside_opacity))
        if self.bounds is not None:
            object.__setattr__(self, "bounds", _normalize_bounds(self.bounds))

    @property
    def outside_alpha(self) -> int:
        """'uint8' alpha value corresponding to 'outside_opacity'."""
        return outside_opacity_to_alpha_uint8(self.outside_opacity)

    def with_clamped_bounds(
        self,
        grid_bounds: Bounds6D | None,
        min_size: float = 1e-3,
    ) -> VisSubRoiState:
        """Return a copy with 'bounds' normalized and clamped to 'grid_bounds'.
        Parameters:
            grid_bounds: World-space "(x_min, x_max, y_min, y_max,
                z_min, z_max)" in micrometers, or 'None' to skip clamping.
            min_size: Minimum allowed size of each axis in micrometers.
        Returns:
            A new 'VisSubRoiState' with normalized and clamped 'bounds'.
        """
        if self.bounds is None:
            return self
        clamped = _clamp_bounds_6d(self.bounds, grid_bounds, min_size=min_size)
        if clamped == self.bounds:
            return self
        return VisSubRoiState(
            enabled=self.enabled,
            bounds=clamped,
            outside_opacity=self.outside_opacity,
        )


def world_bounds_to_normalized_tex_coords(
    roi_bounds: Bounds6D,
    grid_bounds: Bounds6D,
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Map world-space 'roi_bounds' into '[0.0, 1.0]^3' relative to 'grid_bounds'.

    this is used to compute texture coordinates for a Sub-ROI box in the volume renderer
    since the volume renderer uses normalized texture coordinates for the box geometry.

    Accounts for non-zero grid origins and anisotropic axis extents by normalizing
    each axis against '(grid_max - grid_min)'.

    Parameters:
        roi_bounds: World-space "(x_min, x_max, y_min, y_max, z_min, z_max)" in micrometers.
        grid_bounds: World-space "(x_min, x_max, y_min, y_max, z_min, z_max)" in micrometers
            defining the full volume extent.
    Returns:
        A tuple of two 3-tuples: '((u_min_x, u_min_y, u_min_z), (u_max_x, u_max_y, u_max_z))' in
        normalized texture coordinates '[0.0, 1.0]^3' relative to 'grid_bounds'.

    """
    rx0, rx1, ry0, ry1, rz0, rz1 = _normalize_bounds(roi_bounds)
    gx0, gx1, gy0, gy1, gz0, gz1 = _normalize_bounds(grid_bounds)

    # Ensure non-zero axis spans to avoid division by zero, using a small epsilon.
    dx = max(gx1 - gx0, _MIN_AXIS_SPAN)
    dy = max(gy1 - gy0, _MIN_AXIS_SPAN)
    dz = max(gz1 - gz0, _MIN_AXIS_SPAN)

    # u min is the normalized coordinate of the lower corner
    # of the ROI relative to the grid bounds.
    u_min = (
        float(np.clip((rx0 - gx0) / dx, 0.0, 1.0)),
        float(np.clip((ry0 - gy0) / dy, 0.0, 1.0)),
        float(np.clip((rz0 - gz0) / dz, 0.0, 1.0)),
    )
    # u max is the normalized coordinate of the upper corner
    # of the ROI relative to the grid bounds.
    u_max = (
        float(np.clip((rx1 - gx0) / dx, 0.0, 1.0)),
        float(np.clip((ry1 - gy0) / dy, 0.0, 1.0)),
        float(np.clip((rz1 - gz0) / dz, 0.0, 1.0)),
    )
    return u_min, u_max


def compute_inside_mask(
    points_xyz: NDArray[np.floating],
    bounds: Bounds6D,
) -> NDArray[np.bool_]:
    """Return a boolean mask of shape '(N,)' indicating points inside or on 'bounds'.

    it will be used to define which blobs or points of a trajectory are inside the sub-ROI box
    and which are outside.

    Parameters:
        points_xyz: Array of shape '(N, 3)' representing N points in world coordinates
        bounds: World-space "(x_min, x_max, y_min, y_max, z_min, z_max)" in micrometers
        defining the axis-aligned bounding box.
    Returns:
        A boolean array of shape '(N,)' where 'True' indicates the corresponding point is
        inside or on the bounding box defined by 'bounds'.
    """
    pts = np.asarray(points_xyz, dtype=np.float64)
    if pts.size == 0:
        return np.empty(0, dtype=np.bool_)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError(f"Expected points of shape (N, 3), received {pts.shape}.")

    xmin, xmax, ymin, ymax, zmin, zmax = _normalize_bounds(bounds)
    return (
        (pts[:, 0] >= xmin)
        & (pts[:, 0] <= xmax)
        & (pts[:, 1] >= ymin)
        & (pts[:, 1] <= ymax)
        & (pts[:, 2] >= zmin)
        & (pts[:, 2] <= zmax)
    )


def _split_segment_at_aabb(
    p0: NDArray[np.float64],
    p1: NDArray[np.float64],
    bounds: Bounds6D,
) -> list[tuple[float, float, bool]]:
    """Return sorted sub-segment parameter intervals '(t_start, t_end, inside)' in '[0.0, 1.0]'."""
    xmin, xmax, ymin, ymax, zmin, zmax = _normalize_bounds(bounds)
    box_min = (xmin, ymin, zmin)
    box_max = (xmax, ymax, zmax)
    delta = p1 - p0

    ts: list[float] = [0.0, 1.0]
    for axis in range(3):
        d_axis = float(delta[axis])
        if abs(d_axis) > _MIN_AXIS_SPAN:
            p0_axis = float(p0[axis])
            for plane_val in (box_min[axis], box_max[axis]):
                t = (plane_val - p0_axis) / d_axis
                if 0.0 < t < 1.0:
                    ts.append(float(t))

    ts.sort()
    unique_ts: list[float] = [ts[0]]
    for t in ts[1:]:
        if abs(t - unique_ts[-1]) > 1e-9:
            unique_ts.append(t)

    intervals: list[tuple[float, float, bool]] = []
    # i discovered zip to iterate over pairs lol its very useful
    for t_a, t_b in zip(unique_ts[:-1], unique_ts[1:], strict=False):
        mid = p0 + 0.5 * (t_a + t_b) * delta
        inside = bool(compute_inside_mask(mid[None, :], bounds)[0])
        intervals.append((t_a, t_b, inside))
    return intervals


def _iter_polyline_cells(poly: pv.PolyData) -> list[list[int]]:
    """Extract vertex index sequences for each line cell in 'poly'."""
    if poly.n_points == 0 or poly.n_cells == 0:
        return []
    lines = np.asarray(poly.lines, dtype=np.int64)
    polylines: list[list[int]] = []
    idx = 0
    n_entries = len(lines)
    while idx < n_entries:
        count = int(lines[idx])
        start = idx + 1
        end = start + count
        if count >= 2 and end <= n_entries:
            polylines.append([int(v) for v in lines[start:end]])
        idx = end
    return polylines


def build_sub_roi_trajectory_polydata(
    prepared: PreparedTrajectories,
    current_frame: int,
    config: TrajectoryRenderConfig,
    state: VisSubRoiState | None = None,
) -> pv.PolyData:
    """Build display trajectory 'PolyData' with AABB boundary splitting and 'uint8' RGBA.

    When 'state' is 'None', 'state.enabled' is 'False', or 'state.bounds' is 'None',
    delegates to 'build_trajectory_polydata()' and attaches opaque ('alpha=255') 'rgba'.
    When active, splits segments crossing any AABB face and interpolates 'rgb',
    'speed_um_s', and 'frame' while preserving 'track_id' and leaving 'prepared' untouched.
    """

    # Build the base trajectory polydata for the current frame and configuration.
    base_poly = build_trajectory_polydata(prepared, current_frame, config)
    if base_poly.n_points == 0 or base_poly.n_cells == 0:
        return pv.PolyData()

    # i take the base color so that i can make it transparent
    # if the point is outside the sub-ROI box
    base_rgb = np.asarray(base_poly.point_data["rgb"], dtype=np.uint8)
    # state of sub roi
    is_active = state is not None and state.enabled and state.bounds is not None

    # if it is not i return the trajectory with full opacity
    if not is_active:
        rgba = np.empty((base_poly.n_points, 4), dtype=np.uint8)
        rgba[:, :3] = base_rgb
        rgba[:, 3] = 255
        out_poly = base_poly.copy()
        out_poly.point_data["rgba"] = rgba
        return out_poly

    assert state is not None and state.bounds is not None
    bounds = _normalize_bounds(state.bounds)
    out_alpha = state.outside_alpha

    # now i need to split the segments
    # first of all i need to get the points, the colors and the other point data
    src_points = np.asarray(base_poly.points, dtype=np.float64)
    src_rgb = base_rgb.astype(np.float64)
    src_track_id = (
        np.asarray(base_poly.point_data["track_id"], dtype=np.int64)
        if "track_id" in base_poly.point_data
        else np.zeros(base_poly.n_points, dtype=np.int64)
    )
    src_speed = (
        np.asarray(base_poly.point_data["speed_um_s"], dtype=np.float64)
        if "speed_um_s" in base_poly.point_data
        else np.zeros(base_poly.n_points, dtype=np.float64)
    )
    src_frame = (
        np.asarray(base_poly.point_data["frame"], dtype=np.float64)
        if "frame" in base_poly.point_data
        else np.zeros(base_poly.n_points, dtype=np.float64)
    )

    out_pts: list[NDArray[np.float32]] = []
    out_rgba: list[tuple[int, int, int, int]] = []
    out_tids: list[int] = []
    out_speeds: list[float] = []
    out_frames: list[float] = []
    out_cells: list[int] = []
    v_cursor = 0

    # first for iterate over the polylines of the base trajectory
    # polylines are defined by the vertex indices of the base_poly
    for v_indices in _iter_polyline_cells(base_poly):
        # iterate over each segment of the polyline defined by consecutive vertex indices
        # for each segment i get the two points, the two colors
        # the two speeds and the two frames and the track id
        for i in range(len(v_indices) - 1):
            ia, ib = v_indices[i], v_indices[i + 1]
            pa, pb = src_points[ia], src_points[ib]
            rgb_a, rgb_b = src_rgb[ia], src_rgb[ib]
            sp_a, sp_b = float(src_speed[ia]), float(src_speed[ib])
            fr_a, fr_b = float(src_frame[ia]), float(src_frame[ib])
            tid = int(src_track_id[ia])

            # now for each segment i need to split it at the AABB boundaries
            for t0, t1, inside in _split_segment_at_aabb(pa, pb, bounds):
                alpha = 255 if inside else out_alpha
                # for each sub-segment i need to compute the interpolated color, speed, frame and track id
                for t_val in (t0, t1):
                    pt = pa + t_val * (pb - pa)
                    rgb_interp = np.clip(np.rint(rgb_a + t_val * (rgb_b - rgb_a)), 0, 255).astype(np.uint8)
                    out_pts.append(pt.astype(np.float32))
                    out_rgba.append((int(rgb_interp[0]), int(rgb_interp[1]), int(rgb_interp[2]), alpha))
                    out_tids.append(tid)
                    out_speeds.append(sp_a + t_val * (sp_b - sp_a))
                    out_frames.append(fr_a + t_val * (fr_b - fr_a))

                # now i need to add the two new points to the output cells
                out_cells.extend([2, v_cursor, v_cursor + 1])
                v_cursor += 2

    # if there are no output points, return an empty PolyData
    if not out_pts:
        return pv.PolyData()
    # build the output PolyData with the new points, lines, and point data
    split_poly = pv.PolyData(
        np.vstack(out_pts),
        lines=np.asarray(out_cells, dtype=np.int64),
    )
    split_poly.point_data["rgba"] = np.asarray(out_rgba, dtype=np.uint8)
    split_poly.point_data["rgb"] = np.asarray(out_rgba, dtype=np.uint8)[:, :3]
    split_poly.point_data["track_id"] = np.asarray(out_tids, dtype=np.int64)
    split_poly.point_data["speed_um_s"] = np.asarray(out_speeds, dtype=np.float32)
    split_poly.point_data["frame"] = np.asarray(out_frames, dtype=np.float64)
    return split_poly
