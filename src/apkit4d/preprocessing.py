"""Preprocess a raw 3D image volume.

AU: arbitrary units (?)
"""

from dataclasses import asdict, dataclass, fields

import numpy as np
from scipy import ndimage

from apkit4d.image import Image


@dataclass
class PreprocParams:
    """User specified configuration for image preprocessing"""

    # Scale of the Gaussian smoothing denoise along the x, y axes
    denoise_xy_scale_um: float = 0.0

    # Scale of the Gaussian smoothing denoise along the z axis (anisotropic)
    denoise_z_scale_um: float = 0.0

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


# TODO: later remove background on the denoised volume
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
