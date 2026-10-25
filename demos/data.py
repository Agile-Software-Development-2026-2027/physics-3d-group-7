"""
Data for the GUI demos: random data or a real .czi file, behind the same interface.

Both sources give the number of frames, a function that returns the volume of frame t,
the voxel size, and the points and tracks to draw on top of the volume. The demos only
use this interface, so their code is the same for random and real data.

Random data: noise plus a few gaussian spots ("algae") that move with a random walk.
The points are the spot centers and the tracks are their paths, so they match the
volume exactly without running any detection.
"""

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from numpy.typing import NDArray

# similar to the sample files: voxels are about 6 times taller than wide
DEFAULT_VOXEL_UM: tuple[float, float, float] = (18.0, 2.8, 2.8)
ALGA_SIGMA_VOX: tuple[float, float, float] = (1.2, 2.5, 2.5)
ALGA_PEAK: int = 2000
BACKGROUND_MEAN: float = 150.0
BACKGROUND_STD: float = 20.0


@dataclass(frozen=True)
class DemoData:
    """
    Everything a demo needs to show a time series of volumes.

    Attributes:
        name: Short description shown in the window title.
        n_frames: Number of time points.
        frame_shape: (z, y, x) shape of one volume.
        voxel_um: (z, y, x) voxel size in micrometers.
        read_frame: Returns the (z, y, x) volume of frame t.
        points: (n, 4) rows of t, z, y, x in voxels.
        point_info: One row per point, shown when a point is selected.
        tracks: (n, 5) rows of track id, t, z, y, x in voxels (napari tracks format).
    """

    name: str
    n_frames: int
    frame_shape: tuple[int, int, int]
    voxel_um: tuple[float, float, float]
    read_frame: Callable[[int], NDArray[np.uint16]]
    points: NDArray[np.float64]
    point_info: pd.DataFrame
    tracks: NDArray[np.float64]


def load(czi: Path | None = None, blobs: Path | None = None, tracks: Path | None = None) -> DemoData:
    """
    Random data if no file is given, otherwise the .czi file and optionally the legacy outputs.

    Args:
        czi: Optional .czi file.
        blobs: Optional blobs table written by the legacy batch command (parquet).
        tracks: Optional tracks table written by the legacy link command (parquet).

    Returns:
        The data for the demo.
    """
    if czi is None:
        return random_data()
    return czi_data(czi, blobs, tracks)


def random_data(
    n_frames: int = 60,
    frame_shape: tuple[int, int, int] = (20, 128, 128),
    n_algae: int = 12,
    voxel_um: tuple[float, float, float] = DEFAULT_VOXEL_UM,
    seed: int = 0,
) -> DemoData:
    """
    Noise plus gaussian spots that move with a random walk.

    Args:
        n_frames: Number of time points.
        frame_shape: (z, y, x) shape of one volume. A real volume is about (95, 512, 512).
        n_algae: Number of moving spots.
        voxel_um: (z, y, x) voxel size in micrometers.
        seed: Seed of the random generator, so every run shows the same data.

    Returns:
        The random data.
    """
    rng = np.random.default_rng(seed)
    size = np.array(frame_shape, dtype=float)
    start = rng.uniform(0.1 * size, 0.9 * size, size=(n_algae, 3))
    steps = rng.normal(0.0, (0.2, 1.5, 1.5), size=(n_frames, n_algae, 3))
    centers = np.clip(start + np.cumsum(steps, axis=0), 0, size - 1)  # (t, alga, zyx)

    # the noise is generated once and reused, so reading a frame stays fast even for big volumes
    background = rng.normal(BACKGROUND_MEAN, BACKGROUND_STD, size=frame_shape).clip(0).astype(np.uint16)
    spot = _gaussian_spot(ALGA_SIGMA_VOX, ALGA_PEAK)

    def read_frame(t: int) -> NDArray[np.uint16]:
        volume = background.copy()
        for center in centers[t]:
            _add_spot(volume, spot, center)
        return volume

    times = np.repeat(np.arange(n_frames), n_algae)
    ids = np.tile(np.arange(n_algae), n_frames)
    zyx = centers.reshape(-1, 3)
    return DemoData(
        name=f"random data {frame_shape}",
        n_frames=n_frames,
        frame_shape=frame_shape,
        voxel_um=voxel_um,
        read_frame=read_frame,
        points=np.column_stack([times, zyx]),
        point_info=pd.DataFrame({"alga": ids, "frame": times}),
        tracks=np.column_stack([ids, times, zyx]),
    )


def czi_data(path: Path, blobs: Path | None = None, tracks: Path | None = None) -> DemoData:
    """
    A .czi file read one frame at a time with czifile, plus the legacy blobs and tracks if given.

    Args:
        path: The .czi file, with axes T, Z, Y, X.
        blobs: Optional blobs table written by the legacy batch command (parquet).
        tracks: Optional tracks table written by the legacy link command (parquet).

    Returns:
        The data of the file.
    """
    import czifile

    scene = czifile.CziFile(path).scenes[0]
    if scene.dims != ("T", "Z", "Y", "X"):
        raise ValueError(f"expected axes T, Z, Y, X, got {scene.dims}")
    scales = scene.coord_scales  # meters
    n_frames, *frame_shape = scene.shape

    def read_frame(t: int) -> NDArray[np.uint16]:
        return scene(T=t).asarray()

    points = np.empty((0, 4))
    point_info = pd.DataFrame()
    if blobs is not None:
        table = pd.read_parquet(blobs)
        points = table[["frame", "z", "y", "x"]].to_numpy(float)
        point_info = table[["frame", "label", "volume_um3", "mean_intensity"]]
    track_rows = np.empty((0, 5))
    if tracks is not None:
        track_rows = pd.read_parquet(tracks)[["particle", "frame", "z", "y", "x"]].to_numpy(float)

    return DemoData(
        name=path.name,
        n_frames=n_frames,
        frame_shape=(frame_shape[0], frame_shape[1], frame_shape[2]),
        voxel_um=(scales["Z"] * 1e6, scales["Y"] * 1e6, scales["X"] * 1e6),
        read_frame=read_frame,
        points=points,
        point_info=point_info,
        tracks=track_rows,
    )


def _gaussian_spot(sigma: tuple[float, float, float], peak: int) -> NDArray[np.uint16]:
    radius = [int(np.ceil(3 * s)) for s in sigma]
    grids = np.ogrid[tuple(slice(-r, r + 1) for r in radius)]
    squared = sum((g / s) ** 2 for g, s in zip(grids, sigma, strict=True))
    return (peak * np.exp(-0.5 * squared)).astype(np.uint16)


def _add_spot(volume: NDArray[np.uint16], spot: NDArray[np.uint16], center: NDArray[np.float64]) -> None:
    # paste the spot centered on `center`, cutting the parts that fall outside the volume
    radius = np.array(spot.shape) // 2
    low = np.round(center).astype(int) - radius
    vol_low = np.maximum(low, 0)
    vol_high = np.minimum(low + spot.shape, volume.shape)
    spot_low = vol_low - low
    spot_high = spot_low + (vol_high - vol_low)
    volume[tuple(slice(a, b) for a, b in zip(vol_low, vol_high, strict=True))] += spot[
        tuple(slice(a, b) for a, b in zip(spot_low, spot_high, strict=True))
    ]
