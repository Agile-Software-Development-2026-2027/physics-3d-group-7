"""
blobfinder.py
=============
Detection 3D a semi LoG e crescita watershed, senza trackpy.

  1. smoothing gaussiano anisotropo alla scala del blob atteso
  2. risposta -LoG normalizzata di scala (sigma_i² ∂²/∂i² per ogni asse): massima al
     centro di un oggetto di diametro ~d, quasi nulla sul fondo piatto
  3. semi = massimi locali della risposta sopra `threshold`, separati da almeno
     `split` x diametro (footprint ellissoidale, anisotropo come il voxel)
  4. crescita: watershed sullo smoothing a partire dai semi, poi ogni regione tiene solo
     i voxel sopra `grow_frac` x il suo picco (confine relativo, come la
     confine relativo e non soglia globale: cellule deboli e forti hanno la stessa forma)
  5. per ogni segmento: centroide pesato sull'intensita' grezza (non quella preprocessata,
     che la finestra e la gamma deformerebbero), volume, estensione Z, picco

Il diametro Z va dato separatamente da quello XY: nel lightfield 10x/0.45 la PSF assiale
allunga ogni cellula su ~70 µm (~4 slice), molto piu' dei suoi ~10 µm reali.
Per un blob gaussiano in 3D la risposta LoG normalizzata e' massima a sigma = r/√3.
"""

from dataclasses import dataclass, asdict, fields

import numpy as np
import pandas as pd
from scipy import ndimage


@dataclass
class BlobParams:
    diameter_xy_um: float = 15.0
    diameter_z_um: float = 70.0
    threshold: float = 0.1       # sulla risposta -LoG del volume preprocessato [0, 1]
    split: float = 1.0           # distanza minima fra semi, in frazioni del diametro: sotto 1
                                 # la stessa cellula si spezza in piu' blob lungo Z (misurato
                                 # sul file LF4D 10x: a 0.6 il 32% dei blob ha un vicino a
                                 # meno di 8 µm in XY, a 1.0 il 5%)
    grow_frac: float = 0.3       # confine della regione: frazione del picco del segmento
    min_volume_um3: float = 200.0
    max_volume_um3: float = 1e6

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


DET_COLUMNS = ["frame", "label", "z", "y", "x", "z_um", "y_um", "x_um", "volume_um3",
               "n_voxels", "z_extent", "response", "peak", "mean_intensity", "max_intensity"]


def _sigmas(p: BlobParams, voxel):
    """Sigma gaussiana per asse (z, y, x) in voxel, da diametro in µm: sigma = (d/2)/√3."""
    d_um = (p.diameter_z_um, p.diameter_xy_um, p.diameter_xy_um)
    return tuple(max(0.5, (d / 2) / np.sqrt(3) / v) for d, v in zip(d_um, voxel))


def _ellipsoid(radii):
    # per eccesso: in Z il raggio vale ~1.9 slice e arrotondando per difetto la distanza
    # minima fra semi scenderebbe a una sola slice
    r = [max(1, int(np.ceil(x))) for x in radii]
    zz, yy, xx = np.ogrid[-r[0]:r[0] + 1, -r[1]:r[1] + 1, -r[2]:r[2] + 1]
    return (zz / r[0]) ** 2 + (yy / r[1]) ** 2 + (xx / r[2]) ** 2 <= 1.0


def _label_max(labels, values, n_lab):
    """Massimo di `values` per etichetta (0 = fondo). Solo sui voxel etichettati:
    ndimage.maximum per indice costa ~4 s su un volume 95x512x512, questo ~0.05 s."""
    out = np.zeros(n_lab, dtype=np.float32)
    nz = labels > 0
    np.maximum.at(out, labels[nz], values[nz])
    return out


def _label_stats(labels, intensity, n_lab):
    """Per etichetta: n. voxel, centroide pesato sull'intensita' (geometrico se la somma e'
    nulla), media, massimo, estensione Z. Tutto con bincount sui soli voxel etichettati."""
    nz = labels > 0
    zi, yi, xi = np.nonzero(nz)
    lab = labels[nz]
    w = intensity[nz].astype(np.float64)
    n = np.bincount(lab, minlength=n_lab)
    sw = np.bincount(lab, w, minlength=n_lab)
    safe_n = np.maximum(n, 1)
    use_w = sw > 0
    den = np.where(use_w, sw, safe_n)
    out = {"n": n, "mean": sw / safe_n}
    for name, c in (("z", zi), ("y", yi), ("x", xi)):
        out[name] = np.where(use_w, np.bincount(lab, w * c, minlength=n_lab),
                             np.bincount(lab, c, minlength=n_lab)) / den
    mx = np.zeros(n_lab, dtype=np.float64)
    np.maximum.at(mx, lab, w)
    zmin = np.full(n_lab, np.iinfo(np.int64).max)
    zmax = np.full(n_lab, -1)
    np.minimum.at(zmin, lab, zi)
    np.maximum.at(zmax, lab, zi)
    out["max"] = mx
    out["z_extent"] = np.where(n > 0, zmax - zmin + 1, 0)
    return out


def log_response(img: np.ndarray, p: BlobParams, voxel):
    """(smoothing, risposta -LoG normalizzata di scala)."""
    s = _sigmas(p, voxel)
    sm = ndimage.gaussian_filter(img.astype(np.float32, copy=False), s)
    resp = np.zeros_like(sm)
    kernel = np.array([1.0, -2.0, 1.0], dtype=np.float32)
    for ax, sig in enumerate(s):
        resp -= (sig ** 2) * ndimage.correlate1d(sm, kernel, axis=ax, mode="nearest")
    return sm, resp


def find_seeds(resp: np.ndarray, p: BlobParams, voxel, threshold=None):
    """Massimi locali della risposta sopra soglia: array (n, 3) di indici (z, y, x)."""
    d_vox = (p.diameter_z_um / voxel[0], p.diameter_xy_um / voxel[1], p.diameter_xy_um / voxel[2])
    fp = _ellipsoid([p.split * d / 2 for d in d_vox])
    thr = p.threshold if threshold is None else threshold
    peaks = (resp == ndimage.maximum_filter(resp, footprint=fp, mode="nearest")) & (resp > thr)
    return np.argwhere(peaks)


def find_blobs(img: np.ndarray, p: BlobParams, voxel, intensity=None, frame: int = 0,
               offset=(0, 0, 0), return_labels: bool = False):
    """Detection su un volume preprocessato (Z, Y, X) in [0, 1].

    intensity: volume grezzo della stessa ROI per il centroide pesato (default: img).
    offset:    origine della ROI in voxel, per coordinate nel volume intero.
    Ritorna (df, labels o None, seeds_response) — l'ultimo serve all'istogramma dei
    candidati nella GUI.
    """
    from skimage.segmentation import watershed

    sm, resp = log_response(img, p, voxel)
    seeds = find_seeds(resp, p, voxel)
    seed_resp = resp[tuple(seeds.T)] if len(seeds) else np.array([])
    if len(seeds) == 0:
        return pd.DataFrame(columns=DET_COLUMNS), None, seed_resp

    # della risposta LoG servono solo i valori ai semi: liberarla PRIMA del watershed
    # toglie 100 MB dal picco (e' il picco a limitare quanti processi puo' usare il batch)
    del resp
    markers = np.zeros(img.shape, dtype=np.int32)
    markers[tuple(seeds.T)] = np.arange(1, len(seeds) + 1)
    seed_val = sm[tuple(seeds.T)]
    mask = sm > p.grow_frac * float(seed_val.min())
    labels = watershed(-sm, markers, mask=mask)
    del markers, mask

    # confine relativo: ogni regione tiene i voxel sopra grow_frac x il proprio picco
    n_lab = len(seeds) + 1
    peak = _label_max(labels, sm, n_lab)
    labels[sm < p.grow_frac * peak[labels]] = 0

    inten = img if intensity is None else intensity
    st = _label_stats(labels, inten, n_lab)
    idx = np.nonzero(st["n"])[0]
    idx = idx[idx > 0]
    if len(idx) == 0:
        return pd.DataFrame(columns=DET_COLUMNS), (labels if return_labels else None), seed_resp

    vox_vol = float(np.prod(voxel))
    df = pd.DataFrame({
        "frame": frame,
        "label": idx,
        "z": st["z"][idx] + offset[0], "y": st["y"][idx] + offset[1], "x": st["x"][idx] + offset[2],
        "volume_um3": st["n"][idx] * vox_vol,
        "n_voxels": st["n"][idx],
        "z_extent": st["z_extent"][idx],
        "response": seed_resp[idx - 1],
        "peak": peak[idx],
        "mean_intensity": st["mean"][idx],
        "max_intensity": st["max"][idx],
    })
    df["z_um"], df["y_um"], df["x_um"] = df["z"] * voxel[0], df["y"] * voxel[1], df["x"] * voxel[2]
    ok = (df["volume_um3"] >= p.min_volume_um3) & (df["volume_um3"] <= p.max_volume_um3)
    if return_labels:
        labels[np.isin(labels, df.loc[~ok, "label"].values)] = 0
    return df.loc[ok, DET_COLUMNS].reset_index(drop=True), (labels if return_labels else None), seed_resp
