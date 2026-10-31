"""Preprocess a raw 3D image volume.

See the `preprocess` function for more details.
"""

from dataclasses import asdict, dataclass, fields
from enum import Enum

import numpy as np
from scipy import ndimage
from skimage.exposure import equalize_adapthist

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

    # Intensity window for normalization. Narrower -> more contrast
    lowest_intensity: float = 0.0
    highest_intensity: float = 1000.0

    logarithmic_compression_enabled: bool = False

    gamma_correction_to_apply: float = 1.0

    clahe_enabled: bool = False
    clahe_clip: float = 0.01
    clahe_kernel_xy_um: float = 150.0

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
    vol: Image[np.float32], p: PreprocParams, voxel_dim: tuple[float, float, float]
) -> Image[np.float32]:
    """Smooths out `vol` via Gaussian filtering. Averages the noise.

    Args:
        vol: raw 3D volume, not mutated
        p: preprocessing configuration, `denoise_z_um` and `denoise_xy_um` are read
        voxel_dim: voxel size in micrometers

    Returns:
        the denoised image
    """

    if p.denoise_xy_scale_um > 0 or p.denoise_z_scale_um > 0:
        sigmas = sigmas_to_voxels(
            (p.denoise_z_scale_um, p.denoise_xy_scale_um, p.denoise_xy_scale_um), voxel_dim
        )
        vol = ndimage.gaussian_filter(vol, sigmas)
    return vol


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
            smoothed -= bg[:, None, None]

        case BgMode.WIDE_GAUSSIAN:
            # We don't touch the Z axis as it is already elongated and would distort the cell
            sigmas = sigmas_to_voxels((0.0, p.bg_sigma_xy_um, p.bg_sigma_xy_um), voxel_dim)
            smoothed -= ndimage.gaussian_filter(smoothed, sigmas)

    return np.clip(smoothed, 0, None, out=smoothed)  # no allocation


def normalize_intensity(volume: Image[np.float32], p: PreprocParams) -> Image[np.float32]:
    """Normalizes intensities in [0.0, 1.0]"""

    span = max(p.highest_intensity - p.lowest_intensity, 1e-6)
    return np.clip((volume - p.lowest_intensity) / span, 0.0, 1.0, dtype=np.float32)


def logarithmic_compression(volume: Image[np.float32]) -> Image[np.float32]:
    """Highlights dim details and dims bright peaks."""

    k = 1000.0
    return (np.log1p(k * volume) / np.log1p(k)).astype(np.float32)


def gamma_correction(volume: Image[np.float32], p: PreprocParams) -> Image[np.float32]:
    """Applies non-linear gamma correction if gamma != 1.0."""

    if p.gamma_correction_to_apply == 1.0:
        return volume
    return np.power(volume, p.gamma_correction_to_apply, dtype=np.float32)


def clahe(
    volume: Image[np.float32], p: PreprocParams, voxel_dim: tuple[float, float, float]
) -> Image[np.float32]:
    """Applies Contrast Limited Adaptive Histogram Equalization (CLAHE).

    CLAHE is an algorithm for local contrast enhancement.
    """

    kz = max(2, volume.shape[0] // 4)  # at least 2 Z slices
    kxy = max(8, int(round(p.clahe_kernel_xy_um / voxel_dim[1])))

    return equalize_adapthist(volume, kernel_size=(kz, kxy, kxy), clip_limit=float(p.clahe_clip)).astype(
        np.float32
    )


def preprocess(
    vol_roi: Image[np.float32], p: PreprocParams, voxel_dim: tuple[float, float, float]
) -> Image[np.float32]:
    """Applies a preprocessing pipeline on a raw but sliced volume.

    Most of these steps are carried out in arbitrary units (AU).

    Steps:
        1. smooth out high-frequency noise via Gaussian smoothing;
        2. remove background given a strategy;
        3. normalize the intensity of the voxels in the volume so that they are in [0.0, 1.1];
        4. optional logarithmic compression, to lift dim voxels and dim bright ones;
        5. adjust the gamma;
        6. optional CLAHE to maximize local contrast.

    Args:
        vol_roi: a volume already sliced via region of interest (ROI) selection
        p: configuration of the preprocessing
        voxel_dim: size of a voxel in micrometers

    """

    volume = vol_roi.astype(np.float32, copy=True)
    out = denoise(volume, p, voxel_dim)
    out = subtract_background(out, p, voxel_dim)
    out = normalize_intensity(out, p)
    if p.logarithmic_compression_enabled:
        out = logarithmic_compression(out)
    out = gamma_correction(out, p)
    if p.clahe_enabled:
        out = clahe(out, p, voxel_dim)
    return out
