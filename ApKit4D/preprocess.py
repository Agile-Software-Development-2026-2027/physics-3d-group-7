"""
preprocess.py
=============
Catena di preprocessing di un volume (Z, Y, X), nell'ordine:

  1. crop ROI            z/y/x (indici di voxel, estremi inclusi)
  2. denoise             gaussiana anisotropa, sigma in µm
  3. sottrazione fondo   nessuna | percentile per slice | gaussiana larga per slice
  4. finestra            [lo, hi] in AU -> [0, 1]  (il "taglio" dell'istogramma)
  5. log / gamma         compressione della dinamica
  6. CLAHE               equalizzazione adattiva 3D (opzionale, la piu' lenta)

L'uscita e' float32 in [0, 1], la stessa scala per ogni frame: lo e hi sono valori
ASSOLUTI, non percentili ricalcolati frame per frame. Se lo fossero, la soglia del
blob finder cambierebbe significato nel tempo (es. col photobleaching).
I percentili servono solo a proporre lo/hi da un frame di riferimento
(suggest_window).
"""

from dataclasses import dataclass, asdict, fields
from typing import Optional

import numpy as np
from scipy import ndimage

BG_MODES = ("nessuno", "percentile per slice", "gaussiana larga")


@dataclass
class PreprocParams:
    # ROI (None = tutto l'asse)
    z0: Optional[int] = None
    z1: Optional[int] = None
    y0: Optional[int] = None
    y1: Optional[int] = None
    x0: Optional[int] = None
    x1: Optional[int] = None
    # denoise
    denoise_xy_um: float = 0.0
    denoise_z_um: float = 0.0
    # fondo
    bg_mode: str = "nessuno"
    bg_percentile: float = 50.0
    bg_sigma_xy_um: float = 60.0
    # finestra e dinamica
    clip_lo: float = 0.0
    clip_hi: float = 1000.0
    log: bool = False
    gamma: float = 1.0
    # CLAHE
    clahe: bool = False
    clahe_clip: float = 0.01
    clahe_kernel_xy_um: float = 150.0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


def roi_slices(p: PreprocParams, shape):
    """Slice (z, y, x) della ROI, con estremi inclusi e ritagliati sulla shape."""
    out = []
    for (a, b), n in zip(((p.z0, p.z1), (p.y0, p.y1), (p.x0, p.x1)), shape):
        lo = 0 if a is None else max(0, min(int(a), n - 1))
        hi = n - 1 if b is None else max(lo, min(int(b), n - 1))
        out.append(slice(lo, hi + 1))
    return tuple(out)


def roi_offset(p: PreprocParams, shape):
    """Origine della ROI in voxel (z, y, x): serve a riportare le coordinate nel volume intero."""
    return tuple(s.start for s in roi_slices(p, shape))


def _sigma_vox(sigma_um, voxel):
    return tuple(s / v if v > 0 else 0.0 for s, v in zip(sigma_um, voxel))


def subtract_background(v: np.ndarray, p: PreprocParams, voxel) -> np.ndarray:
    if p.bg_mode == "percentile per slice":
        bg = np.percentile(v.reshape(v.shape[0], -1), p.bg_percentile, axis=1)
        v = v - bg[:, None, None]
    elif p.bg_mode == "gaussiana larga":
        # solo in XY: in Z la PSF assiale e' gia' lunga ~4 slice e sfumerebbe la cellula
        s = _sigma_vox((0.0, p.bg_sigma_xy_um, p.bg_sigma_xy_um), voxel)
        v = v - ndimage.gaussian_filter(v, s)
    return np.clip(v, 0, None, out=v)


def denoise_and_background(vol: np.ndarray, p: PreprocParams, voxel) -> np.ndarray:
    """Passi 2-3: resta in AU (float32). Serve anche all'istogramma della finestra."""
    v = vol.astype(np.float32, copy=True)
    if p.denoise_xy_um > 0 or p.denoise_z_um > 0:
        s = _sigma_vox((p.denoise_z_um, p.denoise_xy_um, p.denoise_xy_um), voxel)
        v = ndimage.gaussian_filter(v, s)
    if p.bg_mode != "nessuno":
        v = subtract_background(v, p, voxel)
    return v


def window(v: np.ndarray, p: PreprocParams, voxel) -> np.ndarray:
    """Passi 4-6 su un volume in AU: finestra -> log -> gamma -> CLAHE, uscita in [0, 1]."""
    span = max(float(p.clip_hi) - float(p.clip_lo), 1e-6)
    out = np.clip((v - float(p.clip_lo)) / span, 0.0, 1.0).astype(np.float32)
    if p.log:
        k = 1000.0
        out = np.log1p(k * out) / np.log1p(k)
    if p.gamma != 1.0:
        out = np.power(out, float(p.gamma), dtype=np.float32)
    if p.clahe:
        from skimage.exposure import equalize_adapthist
        # un kernel di un solo voxel in Z non avrebbe senso: almeno 2 slice
        kz = max(2, out.shape[0] // 4)
        kxy = max(8, int(round(p.clahe_kernel_xy_um / voxel[1])))
        out = equalize_adapthist(out, kernel_size=(kz, kxy, kxy),
                                 clip_limit=float(p.clahe_clip)).astype(np.float32)
    return out


def preprocess(vol_roi: np.ndarray, p: PreprocParams, voxel) -> np.ndarray:
    """Volume gia' ritagliato sulla ROI -> float32 [0, 1]."""
    return window(denoise_and_background(vol_roi, p, voxel), p, voxel)


def suggest_window(v: np.ndarray, lo_pct: float = 1.0, hi_pct: float = 99.9,
                   ignore_zeros: bool = True):
    """Proposta di [lo, hi] dai percentili di un volume (in AU).

    I dati lightfield sono zero-inflated (mediana 0 su interi volumi): con gli zeri
    dentro, qualunque percentile basso vale 0 e quelli alti sono spostati in basso.
    """
    x = v[v > 0] if ignore_zeros else v.ravel()
    if x.size == 0:
        return 0.0, 1.0
    if x.size > 2_000_000:  # stima dei percentili su un sottocampione, per reattivita'
        x = np.random.default_rng(0).choice(x, 2_000_000, replace=False)
    lo, hi = np.percentile(x, [lo_pct, hi_pct])
    return float(lo), float(max(hi, lo + 1e-3))
