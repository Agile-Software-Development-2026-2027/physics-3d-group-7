"""Preprocess a raw 3D image volume.

AU: arbitrary units (?)
"""

from dataclasses import asdict, dataclass, fields
from enum import Enum

import numpy as np
from scipy import ndimage

from apkit4d.image import Image


class BgMode(Enum):
    NONE = "None"
    PERCENTILE_PER_SLICE = "Percentile per slice"
    WIDE_GAUSSIAN = "Wide Gaussian"


@dataclass
class PreprocParams:
    """User specified configuration for image preprocessing"""

    # Scale of the Gaussian smoothing denoise along the x, y axes
    denoise_xy_scale_um: float = 0.0

    # Scale of the Gaussian smoothing denoise along the z axis (anisotropic)
    denoise_z_scale_um: float = 0.0

    # Background removal strategy
    bg_mode: BgMode = BgMode.NONE

    # The percentile for BgMode.PERCENTILE_PER_SLICE
    bg_percentile: float = 50.0

    # Sigma scale for the Gaussing smoothing applied when BgMode.WIDE_GAUSSIAN
    bg_sigma_xy_um: float = 60.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


def sigmas_to_voxels(
    sigma_um: tuple[float, float, float], voxel_dim: tuple[float, float, float]
) -> tuple[float, float, float]:
    """Converts the sigmas for the Gaussian filter from micrometers to voxels."""

    sz, sy, sx = sigma_um
    vz, vy, vx = voxel_dim
    return sz / vz if vz > 0 else 0.0, sy / vy if vy > 0 else 0.0, sx / vx if vx > 0 else 0.0


def denoise(
    vol: Image[np.uint16], p: PreprocParams, voxel_dim: tuple[float, float, float]
) -> Image[np.float32]:
    """Smooths out `vol` via Gaussian filtering. Averages the noise.

    Args:
        vol: raw 3D volume, not mutated
        p: preprocessing configuration, `denoise_z_um` and `denoise_xy_um` are read
        voxel_dim: voxel size in micrometers

    Returns:
        the denoised image
    """

    volume = vol.astype(np.float32, copy=True)
    if p.denoise_xy_scale_um > 0 or p.denoise_z_scale_um > 0:
        sigmas = sigmas_to_voxels(
            (p.denoise_z_scale_um, p.denoise_xy_scale_um, p.denoise_xy_scale_um), voxel_dim
        )
        volume = ndimage.gaussian_filter(volume, sigmas)
    return volume


def subtract_background(
    smoothed: Image[np.float32], p: PreprocParams, voxel_dim: tuple[float, float, float]
) -> Image[np.float32]:
    """Removes background noise from the already smoothed volume.

    It does different things based on `p.bg_mode`:
        - BgMode.NONE: identity, returns `smoothed` unchanged
        - BgMode.PERCENTILE_PER_SLICE: takes the Z slices (planes) and subtracts
          the `p.bg_percentile` computed on the slice from every voxel in it.
        - BgMode.WIDE_GAUSSIAN: computes a very coarse Gaussian filter and
          subtracts from the image

    Args:
        smoothed: the image to clean up, it is mutated IN-PLACE (and also returned)
        p: parameters for preprocessing
        voxel_dim: dimension of the voxels in micrometers
    """

    match p.bg_mode:
        case BgMode.NONE:
            return smoothed

        case BgMode.PERCENTILE_PER_SLICE:
            bg = np.percentile(smoothed.reshape(smoothed.shape[0], -1), p.bg_percentile, axis=1)
            smoothed = smoothed - bg[:, None, None]

        case BgMode.WIDE_GAUSSIAN:
            # We don't touch the Z axis as it is already elongated and would distort the cell
            sigmas = sigmas_to_voxels((0.0, p.bg_sigma_xy_um, p.bg_sigma_xy_um), voxel_dim)
            smoothed = smoothed - ndimage.gaussian_filter(smoothed, sigmas)

    return np.clip(smoothed, 0, None, out=smoothed)  # no allocation
