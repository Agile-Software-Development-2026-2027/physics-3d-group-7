import colorsys
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache

import matplotlib
import numpy as np
import pandas as pd
import pyvista as pv
from numpy.typing import NDArray

from apkit4d.image import Image

TRAJECTORY_REQUIRED_COLUMNS: tuple[str, ...] = ("track_id", "frame", "x_um", "y_um", "z_um")
_CATEGORICAL_SATURATION = 0.85
_CATEGORICAL_VALUES = (0.96, 0.84)
_GOLDEN_RATIO = 0.6180339887498949
_SPEED_COLOR_PERCENTILE = 98.0
_LUT_SIZE = 256


class TrajectoryColorMode(StrEnum):
    """Coloring mode for 3D trajectory rendering."""

    SPEED = "speed"
    TRACK_ID = "track_id"


@dataclass(frozen=True)
class TrajectoryRenderConfig:
    """Visual parameters controlling live trajectory rendering.

    Attributes:
        visible: Whether trajectory polylines should be rendered.
        show_blobs: Whether current-frame blob points should be visible.
        tail_length: Maximum trailing step count up to `current_frame`. ``-1`` renders all steps
            from the start of each track; ``0`` renders no polyline trail.
        color_mode: Color encoding scheme (instantaneous speed or categorical track ID).
        colormap: Matplotlib colormap name used when `color_mode` is ``SPEED``.
        line_width: Screen-space line thickness in pixels.
    """

    visible: bool = True
    show_blobs: bool = True
    tail_length: int = -1
    color_mode: TrajectoryColorMode = TrajectoryColorMode.SPEED
    colormap: str = "turbo"
    line_width: float = 2.5


@lru_cache(maxsize=16)
def _colormap_lut(name: str) -> NDArray[np.uint8]:
    """Return a cached `(256, 3)` uint8 RGB lookup table for matplotlib colormap `name`."""
    try:
        cmap = matplotlib.colormaps[name]
    except KeyError:
        cmap = matplotlib.colormaps["turbo"]
    samples = cmap(np.linspace(0.0, 1.0, _LUT_SIZE))[:, :3]
    return np.clip(np.rint(samples * 255.0), 0, 255).astype(np.uint8)


def _track_id_to_rgb(track_id: int) -> tuple[int, int, int]:
    """Return a deterministic high-contrast RGB color for `track_id`."""
    hue = (int(track_id) * _GOLDEN_RATIO) % 1.0
    value = _CATEGORICAL_VALUES[int(track_id) % len(_CATEGORICAL_VALUES)]
    r, g, b = colorsys.hsv_to_rgb(hue, _CATEGORICAL_SATURATION, value)
    return int(round(r * 255)), int(round(g * 255)), int(round(b * 255))


@dataclass(frozen=True)
class PreparedTrajectories:
    """Pre-packed contiguous NumPy buffers for fast per-frame trajectory slicing.

    All arrays share vertex index `0..n_points-1` ordered monotonically by `(track_id, frame)`.
    """

    points_um: NDArray[np.float32]
    frames: NDArray[np.int64]
    track_ids: NDArray[np.int64]
    speeds: NDArray[np.float32]
    categorical_rgb: NDArray[np.uint8]
    speed_vmax: float

    @property
    def n_points(self) -> int:
        """Total number of valid detection vertices across all tracks."""
        return int(len(self.frames))

    @classmethod
    def empty(cls) -> PreparedTrajectories:
        """Return an empty `PreparedTrajectories` container."""
        return cls(
            points_um=np.empty((0, 3), dtype=np.float32),
            frames=np.empty(0, dtype=np.int64),
            track_ids=np.empty(0, dtype=np.int64),
            speeds=np.empty(0, dtype=np.float32),
            categorical_rgb=np.empty((0, 3), dtype=np.uint8),
            speed_vmax=1.0,
        )

    @classmethod
    def from_dataframe(
        cls,
        df: pd.DataFrame | None,
        dt_s: float | None = None,
    ) -> PreparedTrajectories:
        """Validate, sort, and precompute speeds and palette colors for `df` once."""
        if df is None or df.empty:
            return cls.empty()

        missing = [col for col in TRAJECTORY_REQUIRED_COLUMNS if col not in df.columns]
        if missing:
            raise ValueError(f"Trajectory DataFrame is missing required columns: {missing}")

        subset_cols = list(TRAJECTORY_REQUIRED_COLUMNS)
        has_time = "t_s" in df.columns
        if has_time:
            subset_cols.append("t_s")

        clean = df[subset_cols].copy()
        for col in TRAJECTORY_REQUIRED_COLUMNS:
            clean[col] = pd.to_numeric(clean[col], errors="coerce")
        if has_time:
            clean["t_s"] = pd.to_numeric(clean["t_s"], errors="coerce")

        clean = clean.dropna(subset=list(TRAJECTORY_REQUIRED_COLUMNS))
        clean = clean[clean["track_id"] >= 0]
        if clean.empty:
            return cls.empty()

        clean["track_id"] = clean["track_id"].astype(np.int64)
        clean["frame"] = clean["frame"].astype(np.int64)
        clean = clean.sort_values(["track_id", "frame"], kind="mergesort").reset_index(drop=True)

        points_um = clean[["x_um", "y_um", "z_um"]].to_numpy(dtype=np.float32)
        frames = clean["frame"].to_numpy(dtype=np.int64)
        track_ids = clean["track_id"].to_numpy(dtype=np.int64)
        t_s = clean["t_s"].to_numpy(dtype=np.float64) if has_time else None

        speeds = _compute_point_speeds(points_um, frames, track_ids, t_s=t_s, dt_s=dt_s)
        positive_speeds = speeds[speeds > 0]
        speed_vmax = (
            float(np.percentile(positive_speeds, _SPEED_COLOR_PERCENTILE))
            if len(positive_speeds) > 0
            else 1.0
        )
        if not np.isfinite(speed_vmax) or speed_vmax <= 1e-9:
            speed_vmax = 1.0

        unique_ids, inverse = np.unique(track_ids, return_inverse=True)
        palette = np.asarray([_track_id_to_rgb(int(tid)) for tid in unique_ids], dtype=np.uint8)
        categorical_rgb = palette[inverse]

        return cls(
            points_um=np.ascontiguousarray(points_um),
            frames=np.ascontiguousarray(frames),
            track_ids=np.ascontiguousarray(track_ids),
            speeds=np.ascontiguousarray(speeds),
            categorical_rgb=np.ascontiguousarray(categorical_rgb),
            speed_vmax=speed_vmax,
        )


def _compute_point_speeds(
    points_um: NDArray[np.float32],
    frames: NDArray[np.int64],
    track_ids: NDArray[np.int64],
    *,
    t_s: NDArray[np.float64] | None,
    dt_s: float | None,
) -> NDArray[np.float32]:
    """Compute instantaneous speed in um/s at each sorted trajectory vertex."""
    n = len(frames)
    speeds = np.zeros(n, dtype=np.float32)
    if n < 2:
        return speeds

    same_track = track_ids[1:] == track_ids[:-1]
    disp = np.linalg.norm(points_um[1:].astype(np.float64) - points_um[:-1].astype(np.float64), axis=1)

    fallback_dt = float(dt_s) if dt_s is not None and dt_s > 0 else 1.0
    dt = (frames[1:] - frames[:-1]).astype(np.float64) * fallback_dt
    if t_s is not None:
        dt_from_t = t_s[1:] - t_s[:-1]
        valid_t = np.isfinite(dt_from_t) & (dt_from_t > 0)
        dt = np.where(valid_t, dt_from_t, dt)

    valid_seg = same_track & (dt > 0)
    seg_speed = np.zeros(n - 1, dtype=np.float64)
    seg_speed[valid_seg] = disp[valid_seg] / dt[valid_seg]

    speeds[1:] = np.where(same_track, seg_speed, 0.0).astype(np.float32)

    # Propagate each multi-point track's initial segment speed onto its starting vertex.
    track_start_mask = np.empty(n, dtype=bool)
    track_start_mask[0] = True
    track_start_mask[1:] = ~same_track
    start_indices = np.flatnonzero(track_start_mask)
    has_next = (start_indices + 1) < n
    valid_starts = start_indices[has_next]
    next_same = track_ids[valid_starts + 1] == track_ids[valid_starts]
    multi_starts = valid_starts[next_same]
    speeds[multi_starts] = speeds[multi_starts + 1]
    return speeds


def build_trajectory_polydata(
    prepared: PreparedTrajectories,
    current_frame: int,
    config: TrajectoryRenderConfig,
) -> pv.PolyData:
    """Slice `prepared` up to `current_frame` with `config.tail_length` and build grouped polylines."""
    if not config.visible or prepared.n_points == 0 or config.tail_length == 0:
        return pv.PolyData()

    max_frame = int(current_frame)
    mask = prepared.frames <= max_frame
    if config.tail_length > 0:
        mask &= prepared.frames >= (max_frame - int(config.tail_length))

    if np.count_nonzero(mask) < 2:
        return pv.PolyData()

    kept_idx = np.flatnonzero(mask)
    kept_tids = prepared.track_ids[kept_idx]
    change_pos = np.flatnonzero(kept_tids[1:] != kept_tids[:-1]) + 1
    starts = np.r_[0, change_pos]
    ends = np.r_[change_pos, len(kept_tids)]
    counts = ends - starts

    valid_seg_mask = counts >= 2
    if not np.any(valid_seg_mask):
        return pv.PolyData()

    valid_counts = counts[valid_seg_mask]
    if not np.all(valid_seg_mask):
        # Drop isolated single-point detections so PolyData only keeps points belonging to lines.
        keep_vertex = np.repeat(valid_seg_mask, counts)
        kept_idx = kept_idx[keep_vertex]

    n_vertices = len(kept_idx)
    n_tracks = len(valid_counts)
    cells = np.empty(n_tracks + n_vertices, dtype=np.int64)
    header_pos = np.arange(n_tracks, dtype=np.int64) + np.r_[0, np.cumsum(valid_counts[:-1])]
    cells[header_pos] = valid_counts
    vertex_slots = np.ones(len(cells), dtype=bool)
    vertex_slots[header_pos] = False
    cells[vertex_slots] = np.arange(n_vertices, dtype=np.int64)

    poly = pv.PolyData(prepared.points_um[kept_idx], lines=cells)
    poly.point_data["rgb"] = _resolve_trajectory_rgb(prepared, kept_idx, config)
    poly.point_data["track_id"] = prepared.track_ids[kept_idx]
    poly.point_data["speed_um_s"] = prepared.speeds[kept_idx]
    poly.point_data["frame"] = prepared.frames[kept_idx]
    return poly


def _resolve_trajectory_rgb(
    prepared: PreparedTrajectories,
    indices: NDArray[np.int64],
    config: TrajectoryRenderConfig,
) -> NDArray[np.uint8]:
    """Compute per-vertex `uint8` RGB colors for the selected trajectory indices."""
    if config.color_mode == TrajectoryColorMode.TRACK_ID:
        return np.ascontiguousarray(prepared.categorical_rgb[indices])

    lut = _colormap_lut(config.colormap)
    norm = np.clip(prepared.speeds[indices] / max(prepared.speed_vmax, 1e-6), 0.0, 1.0)
    bins = np.rint(norm * (_LUT_SIZE - 1)).astype(np.int64)
    return np.ascontiguousarray(lut[bins])


def create_volume_grid(
    img_array: Image[np.uint16],
    voxel_size: tuple[float, float, float],
    offset: tuple[float, float, float] = (0, 0, 0),
) -> pv.ImageData:
    """
    Create a PyVista ImageData object from a 3D numpy array.

    Parameters:
        img_array (np.ndarray): 3D numpy array representing the volume data.

        voxel_size (tuple): Size of each voxel in the format (z_size, y_size, x_size).

        offset (tuple): Offset for the grid in the format (z_offset, y_offset, x_offset).

        this offset is used to shift the grid in space for future visualization purposes (Ex. ROI selection).

    Returns:
        pv.ImageData: PyVista ImageData object representing the volume grid.
    """

    if img_array is None or img_array.size == 0 or img_array.ndim != 3:
        return pv.ImageData()

    # the intensities are read as uint16 from the CZI, we need them as float32
    img_float = img_array.astype(np.float32, copy=False)

    # transpose the array to match PyVista's expected order
    img_xyz = np.transpose(img_float, (2, 1, 0))

    # transpose the voxel size to match the order of the transposed array
    spacing_xyz = (voxel_size[2], voxel_size[1], voxel_size[0])

    grid = pv.ImageData(dimensions=img_xyz.shape, spacing=spacing_xyz, origin=offset)

    """
        VTK do not accept 3d numpy array as point data so we need to flatten the array,
        with order='F' (X axe first)

        point_data is a dictionary-like object that allows you to store additional data,
        associated with the points of the grid.
        we use this to store the flattened image data as point data in the grid
    """
    grid.point_data["values"] = img_xyz.flatten(order="F")
    return grid


def create_blob_mesh(df: pd.DataFrame) -> pv.PolyData:
    """
    This function is used to create the blobs that will be visualized in the 3D space.

    it creates a PyVista PolyData object from a pandas DataFrame containing blob data.
    every row in the DataFrame represents a blob,
    and the columns contain the necessary information to create the mesh.

    Parameters:
        df (pd.DataFrame): DataFrame containing blob data.
        The columns contain the following information:
            - frame: temporal frame index of the image
            - label: unique identifier for the segmented blob
            - z, y, x: centroid coordinates in voxel units (including ROI offset)
            - z_um, y_um, x_um: absolute spatial coordinates of the centroid in micrometers
            - volume_um3: physical volume of the blob in cubic micrometers
            - n_voxels: total number of voxels belonging to the segmented blob
            - z_extent: z dimension of the blob
            - response: number that represents the strenght of the signal
            (how the algorithm is confident that this is a blob)
            - peak: maximum intensity on the smoothed image within the blob's region
            - mean_intensity: average pixel intensity of the raw image within the blob
            - max_intensity: maximum pixel intensity of the raw image within the blob

    Returns:
        pv.PolyData: PyVista PolyData object representing the blobs as spheres in 3D space.

    """
    if df is None or df.empty:
        return pv.PolyData()

    coordinates = df[["x_um", "y_um", "z_um"]].to_numpy()
    poly = pv.PolyData(coordinates)

    column_to_exclude = {"x_um", "y_um", "z_um"}
    # Add the remaining columns as point data to the PolyData object
    for column in df.columns:
        if column not in column_to_exclude:
            poly.point_data[column] = df[column].to_numpy()

    return poly
