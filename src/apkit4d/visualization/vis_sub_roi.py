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
DEFAULT_BLOB_RGB: tuple[int, int, int] = (255, 0, 0)
_MIN_AXIS_SPAN: float = 1e-12
_SEGMENT_T_EPS: float = 1e-9


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


def build_sub_roi_blobs_polydata(
    blobs: pv.PolyData | None,
    state: VisSubRoiState | None = None,
    *,
    base_rgb: tuple[int, int, int] = DEFAULT_BLOB_RGB,
) -> pv.PolyData:
    """Build a display-only blob 'PolyData' with per-point 'uint8' RGBA opacity.

    Returns a deep copy with 'rgba' point scalars so caller PolyData and NumPy buffers
    are never mutated. When 'state' is inactive, all points have full opacity (255).

    Parameters:
        blobs: Input blob 'PolyData' with any number of points.
        state: Optional 'VisSubRoiState' controlling Sub-ROI attenuation.
        base_rgb: RGB color to apply to all points, clamped to [0, 255] and converted to 'uint8'.
    Returns:
        A new 'PolyData' with the same points and a new 'rgba' point array of shape '(N, 4)'
        where 'N' is the number of points in 'blobs'.
    """
    if blobs is None or blobs.n_points == 0:
        return pv.PolyData()

    out_poly = blobs.copy(deep=True)
    n_points = out_poly.n_points
    rgba = np.empty((n_points, 4), dtype=np.uint8)
    rgba[:, 0] = int(np.clip(base_rgb[0], 0, 255))
    rgba[:, 1] = int(np.clip(base_rgb[1], 0, 255))
    rgba[:, 2] = int(np.clip(base_rgb[2], 0, 255))

    if state is not None and state.enabled and state.bounds is not None:
        # compute a boolean mask indicating which points are inside the Sub-ROI bounds
        inside = compute_inside_mask(np.asarray(out_poly.points, dtype=np.float64), state.bounds)
        # set the alpha channel to 255 for points inside and to 'outside_alpha' for points outside
        rgba[:, 3] = np.where(inside, 255, state.outside_alpha).astype(np.uint8)
    else:
        rgba[:, 3] = 255

    # attach the 'rgba' array to the output PolyData and set it as the active scalars
    out_poly.point_data["rgba"] = rgba
    out_poly.set_active_scalars("rgba", preference="point")
    return out_poly


def _split_segment_at_aabb(
    p0: NDArray[np.float64],
    p1: NDArray[np.float64],
    bounds: Bounds6D,
) -> list[tuple[float, float, bool]]:
    """Return non-degenerate sorted sub-segment intervals '(t_start, t_end, inside)' in '[0.0, 1.0]'.

    i changed this function to slab clipping algorithm so that i can determine directly t_enter and
    t_exit for the segment and then return the intervals based on that.
    """
    xmin, xmax, ymin, ymax, zmin, zmax = _normalize_bounds(bounds)
    box_min = (xmin, ymin, zmin)
    box_max = (xmax, ymax, zmax)
    delta = p1 - p0

    t_enter = 0.0
    t_exit = 1.0
    for axis in range(3):
        d_axis = float(delta[axis])
        p0_axis = float(p0[axis])
        lo = box_min[axis]
        hi = box_max[axis]
        # if the segment is parallel to the axis, check if it is outside the box
        if abs(d_axis) <= _MIN_AXIS_SPAN:
            if p0_axis < lo or p0_axis > hi:
                return [(0.0, 1.0, False)]
        else:
            # for each axis i compute the intersections interval similar to the
            # slab method for ray-box intersection
            inv_d = 1.0 / d_axis
            t1 = (lo - p0_axis) * inv_d
            t2 = (hi - p0_axis) * inv_d
            t_near = min(t1, t2)
            t_far = max(t1, t2)
            t_enter = max(t_enter, t_near)
            t_exit = min(t_exit, t_far)
            # if the segment is completely outside the box, return a single interval
            # with inside=False
            if t_enter > t_exit:
                return [(0.0, 1.0, False)]

    # if the segment is almost null we do not create any sub-segment and return a single
    # interval with inside=False
    if t_exit - t_enter <= _SEGMENT_T_EPS:
        return [(0.0, 1.0, False)]

    intervals: list[tuple[float, float, bool]] = []
    if t_enter > _SEGMENT_T_EPS:
        intervals.append((0.0, float(t_enter), False))
    else:
        t_enter = 0.0

    if 1.0 - t_exit > _SEGMENT_T_EPS:
        intervals.append((float(t_enter), float(t_exit), True))
        intervals.append((float(t_exit), 1.0, False))
    else:
        intervals.append((float(t_enter), 1.0, True))

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


"""
    i've splitted the construction of trajectories and the application of the sub_roi to make 
    it easier and avoid to rebuild the trajectory polydata.

    Imagine that the viewport has already built the trajectory polydata and then 
    the user activates the sub_roi, we don't want to rebuild the trajectory polydata again, 
    we just want to apply the sub_roi to it. splitting allows us to do that.
"""


def apply_vis_sub_roi_to_trajectories(
    base_poly: pv.PolyData | None,
    state: VisSubRoiState | None = None,
) -> pv.PolyData:
    """Apply Visualization Sub-ROI splitting and 'uint8' RGBA opacity to a trajectory 'PolyData'.

    Never mutates 'base_poly'. When 'state' is inactive, returns a deep copy preserving the
    original polyline topology and exact RGB colors with full alpha (255). When active, splits
    segments crossing AABB faces and assigns alpha 255 inside and 'state.outside_alpha' outside.
    """
    if base_poly is None or base_poly.n_points == 0 or base_poly.n_cells == 0:
        return pv.PolyData()

    # we now accept either 'rgb' or 'rgba' point_data,
    #  but we will always work with 'rgb' for interpolation
    if "rgb" in base_poly.point_data:
        base_rgb = np.ascontiguousarray(base_poly.point_data["rgb"], dtype=np.uint8)
    elif "rgba" in base_poly.point_data:
        base_rgb = np.ascontiguousarray(np.asarray(base_poly.point_data["rgba"], dtype=np.uint8)[:, :3])
    else:
        raise ValueError("Trajectory PolyData must contain 'rgb' or 'rgba' point_data.")

    is_active = state is not None and state.enabled and state.bounds is not None
    if not is_active:
        # deep copy to guarantee that the returned PolyData is independent
        # of the input, even when no splitting is needed
        out_poly = base_poly.copy(deep=True)
        rgba = np.empty((out_poly.n_points, 4), dtype=np.uint8)
        rgba[:, :3] = base_rgb
        rgba[:, 3] = 255
        out_poly.point_data["rgba"] = rgba
        # we set the active scalars to 'rgba' to ensure that when sub-roi is not active
        # we still have the correct color representation for the trajectories
        out_poly.set_active_scalars("rgba", preference="point")
        return out_poly

    assert state is not None and state.bounds is not None
    bounds = _normalize_bounds(state.bounds)
    out_alpha = state.outside_alpha

    src_points = np.asarray(base_poly.points, dtype=np.float64)
    src_rgb_f64 = base_rgb.astype(np.float64)

    # in the prevoius version we were creating alwayst the 3 arrays
    # even if they were not present in the base_poly, now we check if they are present
    # and only create them if they are.
    has_track_id = "track_id" in base_poly.point_data
    has_speed = "speed_um_s" in base_poly.point_data
    has_frame = "frame" in base_poly.point_data

    src_track_id = np.asarray(base_poly.point_data["track_id"], dtype=np.int64) if has_track_id else None
    src_speed = np.asarray(base_poly.point_data["speed_um_s"], dtype=np.float64) if has_speed else None
    src_frame = np.asarray(base_poly.point_data["frame"], dtype=np.float64) if has_frame else None

    out_pts: list[NDArray[np.float32]] = []
    out_rgba: list[tuple[int, int, int, int]] = []
    out_tids: list[int] = []
    out_speeds: list[float] = []
    out_frames: list[float] = []
    out_cells: list[int] = []
    v_cursor = 0

    for v_indices in _iter_polyline_cells(base_poly):
        for i in range(len(v_indices) - 1):
            ia, ib = v_indices[i], v_indices[i + 1]
            pa, pb = src_points[ia], src_points[ib]
            rgb_a_u8, rgb_b_u8 = base_rgb[ia], base_rgb[ib]
            rgb_a_f64, rgb_b_f64 = src_rgb_f64[ia], src_rgb_f64[ib]
            tid = int(src_track_id[ia]) if src_track_id is not None else 0
            sp_a = float(src_speed[ia]) if src_speed is not None else 0.0
            sp_b = float(src_speed[ib]) if src_speed is not None else 0.0
            fr_a = float(src_frame[ia]) if src_frame is not None else 0.0
            fr_b = float(src_frame[ib]) if src_frame is not None else 0.0

            for t0, t1, inside in _split_segment_at_aabb(pa, pb, bounds):
                alpha = 255 if inside else out_alpha
                # we now iterate over the two endpoints of the sub-segment and compute the interpolated
                # position, color, speed, and frame values for each endpoint.
                for t_val in (t0, t1):
                    if t_val == 0.0:
                        pt = pa.astype(np.float32)
                        r, g, b = int(rgb_a_u8[0]), int(rgb_a_u8[1]), int(rgb_a_u8[2])
                        speed_val = sp_a
                        frame_val = fr_a
                    elif t_val == 1.0:
                        pt = pb.astype(np.float32)
                        r, g, b = int(rgb_b_u8[0]), int(rgb_b_u8[1]), int(rgb_b_u8[2])
                        speed_val = sp_b
                        frame_val = fr_b
                    else:
                        pt = (pa + t_val * (pb - pa)).astype(np.float32)
                        rgb_interp = np.clip(
                            np.rint(rgb_a_f64 + t_val * (rgb_b_f64 - rgb_a_f64)), 0, 255
                        ).astype(np.uint8)
                        r, g, b = int(rgb_interp[0]), int(rgb_interp[1]), int(rgb_interp[2])
                        speed_val = sp_a + t_val * (sp_b - sp_a)
                        frame_val = fr_a + t_val * (fr_b - fr_a)

                    out_pts.append(pt)
                    out_rgba.append((r, g, b, alpha))
                    if has_track_id:
                        out_tids.append(tid)
                    if has_speed:
                        out_speeds.append(speed_val)
                    if has_frame:
                        out_frames.append(frame_val)

                # extend the out_cells with the new 2 points
                out_cells.extend([2, v_cursor, v_cursor + 1])
                v_cursor += 2

    # if there are no output points, return an empty PolyData
    if not out_pts:
        return pv.PolyData()

    # build the output PolyData with the new points, lines, and point data
    rgba_arr = np.asarray(out_rgba, dtype=np.uint8)
    split_poly = pv.PolyData(
        np.vstack(out_pts),
        lines=np.asarray(out_cells, dtype=np.int64),
    )
    split_poly.point_data["rgba"] = rgba_arr
    split_poly.point_data["rgb"] = np.ascontiguousarray(rgba_arr[:, :3])
    if has_track_id:
        split_poly.point_data["track_id"] = np.asarray(out_tids, dtype=np.int64)
    if has_speed:
        split_poly.point_data["speed_um_s"] = np.asarray(out_speeds, dtype=np.float32)
    if has_frame:
        split_poly.point_data["frame"] = np.asarray(out_frames, dtype=np.float64)
    split_poly.set_active_scalars("rgba", preference="point")
    return split_poly


def build_sub_roi_trajectory_polydata(
    prepared: PreparedTrajectories,
    current_frame: int,
    config: TrajectoryRenderConfig,
    state: VisSubRoiState | None = None,
) -> pv.PolyData:
    """Build display trajectory 'PolyData' with AABB boundary splitting and 'uint8' RGBA."""
    base_poly = build_trajectory_polydata(prepared, current_frame, config)
    return apply_vis_sub_roi_to_trajectories(base_poly, state)
