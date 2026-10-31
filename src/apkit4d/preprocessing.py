"""Preprocess a raw 3D image volume.

This happens after ROI slicing and before blob detection.

See the `preprocess` function for more details on the pipeline.

Memory copies and allocations are avoided as much as possible during the
preprocessing sub-pipeline.

RefactorNote:
    BgMode was updated to inherit from enum.StrEnum, this allows native string representation,
    JSON serialization while mantaining backward compatibility with enum comparison.
"""

from dataclasses import asdict, dataclass, fields
from enum import StrEnum

import numpy as np
from scipy import ndimage
from skimage.exposure import equalize_adapthist

from apkit4d.image import Image


class BgMode(StrEnum):
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

    # If equal to 1.0, has no effect
    gamma_correction_to_apply: float = 1.0

    clahe_enabled: bool = False

    # Controls noise amplification
    clahe_clip: float = 0.01

    # Size micrometers of the local neighborhood (tile) used in CLAHE.
    clahe_kernel_xy_um: float = 150.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in (d or {}).items() if k in names}
        if "bg_mode" in kwargs and kwargs["bg_mode"] is not None:
            kwargs["bg_mode"] = BgMode(kwargs["bg_mode"])
        return cls(**kwargs)


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
        vol = ndimage.gaussian_filter(vol, sigmas, output=vol)
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
    volume -= p.lowest_intensity
    volume /= span
    return np.clip(volume, 0.0, 1.0, dtype=np.float32, out=volume)


def logarithmic_compression(volume: Image[np.float32]) -> Image[np.float32]:
    """Highlights dim details and dims bright peaks."""

    k = 1000.0
    np.multiply(volume, k, out=volume)
    np.log1p(volume, out=volume)
    volume /= np.log1p(k)
    return volume


def gamma_correction(volume: Image[np.float32], p: PreprocParams) -> Image[np.float32]:
    """Applies non-linear gamma correction if gamma != 1.0."""

    if p.gamma_correction_to_apply == 1.0:
        return volume
    return np.power(volume, p.gamma_correction_to_apply, dtype=np.float32, out=volume)


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

    Returns:
        the preprocessed image withe the intensity values in [0, 1]
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


def suggest_window(
    volume: Image[np.float32],
    low_percentile: float = 1.0,
    high_percentile: float = 99.9,
    ignore_zeros: bool = True,
) -> tuple[float, float]:
    """Proposes [lowest_intensity, highest_intensity] from the percentiles of a volume.
    This is the intensity windows used for normalization. Its breadth controls contrast.

    I dati lightfield sono zero-inflated (mediana 0 su interi volumi): con gli zeri
    dentro, qualunque percentile basso vale 0 e quelli alti sono spostati in basso.

    Args:
        volume: raw image volume
        low_percentile: bottom of the intensity scale
        high_percentile: top of the itnensity scale
        ignore_zeroes: whether to ignore the nil voxels in `volume`

    Returns:
        the range (lowest_intensity, highest_intensity) in arbitrary units
    """

    x = volume[volume > 0] if ignore_zeros else volume.ravel()
    if x.size == 0:
        return 0.0, 1.0

    # percentile estimate on a subsample if x is too big
    if x.size > 2_000_000:
        x = np.random.default_rng(0).choice(x, 2_000_000, replace=False)

    lo, hi = np.percentile(x, [low_percentile, high_percentile])
    return lo, max(hi, lo + 1e-3)
