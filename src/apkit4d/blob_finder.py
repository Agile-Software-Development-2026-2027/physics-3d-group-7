"""Detect blobs in an already preprocessed 3D image volume.

Voxel: 3-dimensional pixel.

Seeds are the centers of the blobs. Blobs are ellipsoids.

Something is _anisotropic_ if it has properties that depend on the direction of measurement.

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

from dataclasses import asdict, dataclass, fields

import numpy as np
import pandas as pd
from scipy import ndimage
from skimage.segmentation import watershed

SQRT_3 = np.sqrt(3)

# The 3d volume read from the CZI. Goes through prepocessing before running blob finding over it
type Image = np.ndarray[tuple[int, int, int], np.dtype[np.float32]]


@dataclass
class BlobParams:
    """User specified configuration for blob finding"""

    diameter_xy_um: float = 15.0
    diameter_z_um: float = 70.0  # structures are usually elongated on the Z axis

    # soglia risposta log
    threshold: float = 0.1  # sulla risposta -LoG del volume preprocessato [0, 1]

    split: float = 1.0  # distanza minima fra semi, in frazioni del diametro: sotto 1

    # la stessa cellula si spezza in piu' blob lungo Z (misurato
    # sul file LF4D 10x: a 0.6 il 32% dei blob ha un vicino a
    # meno di 8 µm in XY, a 1.0 il 5%)

    grow_frac: float = 0.3  # confine della regione: frazione del picco del segmento

    min_volume_um3: float = 200.0
    max_volume_um3: float = 1e6

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


DET_COLUMNS = [
    "frame",
    "label",
    "z",
    "y",
    "x",
    "z_um",
    "y_um",
    "x_um",
    "volume_um3",
    "n_voxels",
    "z_extent",
    "response",
    "peak",
    "mean_intensity",
    "max_intensity",
]


def _sigmas(p: BlobParams, voxel_dims: tuple[float, float, float]) -> tuple[float, float, float]:
    """Returns the filter scales to use in the LoG.

    Scales the standard deviations σ for each axis (z, y, x), converting from
    diameters in µm to voxels.

    The radius of each blob matches LoG filter scale σ via the relation r=√3·σ
    (in the case of 3 dimensions), so σ=r/√3, where r=d/2.
    Cfr: <https://pydocs.github.io/p/skimage/0.17.2/api/skimage.feature.blob.blob_log.html>
    """

    dz, dy, dx = p.diameter_z_um, p.diameter_xy_um, p.diameter_xy_um
    vz, vy, vx = voxel_dims
    return (
        max(0.5, (dz / 2) / SQRT_3 / vz),
        max(0.5, (dy / 2) / SQRT_3 / vy),
        max(0.5, (dx / 2) / SQRT_3 / vx),
    )


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
        out[name] = (
            np.where(use_w, np.bincount(lab, w * c, minlength=n_lab), np.bincount(lab, c, minlength=n_lab))
            / den
        )
    mx = np.zeros(n_lab, dtype=np.float64)
    np.maximum.at(mx, lab, w)
    zmin = np.full(n_lab, np.iinfo(np.int64).max)
    zmax = np.full(n_lab, -1)
    np.minimum.at(zmin, lab, zi)
    np.maximum.at(zmax, lab, zi)
    out["max"] = mx
    out["z_extent"] = np.where(n > 0, zmax - zmin + 1, 0)
    return out


def log_response(
    img: Image,
    p: BlobParams,
    voxel_dim: tuple[float, float, float],
) -> tuple[Image, Image]:
    """Computes the opposite of the Laplacian of the Gaussian (-LoG) response
    for a 3D image volume.

    The LoG will produce a very strong negative response near bright blobs and
    a very strong positive response near dark blobs, dependening on the radius.
    That's why we use the opposite.

    Intuitively, the Gaussian smooths things out a bit and then with the
    Laplacian we detect how the points in our space increases/decreases in
    brightness in neighborhoods of potential blobs:

        "Informally, the Laplacian Δf(p) of a function f at a point p measures
        by how much the average value of f over small spheres or balls centered
        at p deviates from f(p)."

    Cfr: <https://en.wikipedia.org/wiki/Blob_detection#The_Laplacian_of_Gaussian>

    Args:
        img: the 3D image volume
        p: configuration of the detection
        voxel_dim: dimension of the voxel for each axis (z, y, x)

    Returns:
        A pair containing the smoothed image volume and the scale-normalized
        -LoG response volume. The local maxima on the -LoG response corresponds
        to the centers of the cells.
    """

    # Apply Gaussian smoothing along the three axes using our sigmas. Removes
    # noise and moves everything to the scale of the sigmas, which are in turn
    # influenced by the radii.
    sigmas = _sigmas(p, voxel_dim)
    smoothed = ndimage.gaussian_filter(img.astype(np.float32, copy=False), sigmas)

    # Convolution via Gaussian kernel, plus scale-normalization (mul by σ²).
    # The kernel is symmetric so cross-correlation and convolution are the same here.
    # Summing the second derivative across all axes gives us the Laplacian operator.
    response = np.zeros_like(smoothed)
    kernel = [1.0, -2.0, 1.0]  # second-derivative kernel
    for ax, sigma in enumerate(sigmas):
        response -= (sigma**2) * ndimage.correlate1d(smoothed, weights=kernel, axis=ax, mode="nearest")
    return smoothed, response


def _ellipsoid(radii: tuple[float, float, float]) -> np.ndarray[tuple[int, int, int], np.dtype[np.bool_]]:
    """Creates an ellipsoid in a space of boolean points.

    Args:
        radii: of the ellipsoid along the (z, y, x) axes.

    Returns:
        A 3d image volume. Points in the space that are inside and on the
        surface of the ellipsoid are True, all other points are False.
    """

    # per eccesso: in Z il raggio vale ~1.9 slice e arrotondando per difetto la distanza
    # minima fra semi scenderebbe a una sola slice

    rz, ry, rx = (max(1, int(np.ceil(r))) for r in radii)  # center is (rz, ry, rx)
    zz, yy, xx = np.ogrid[-rz : rz + 1, -ry : ry + 1, -rx : rx + 1]
    return (zz / rz) ** 2 + (yy / ry) ** 2 + (xx / rx) ** 2 <= 1.0


def find_seeds(
    response: Image, p: BlobParams, voxel_dim: tuple[float, float, float], threshold: float | None = None
) -> np.ndarray[tuple[int, int], np.dtype[np.int64]]:
    """Identifies the the local maxima in the -LoG response, i.e. the center of blobs.

    Args:
        response: the -LoG response computed over the 3D image volume
        p: the blob finding configuration, `split` and `threshold` are considered
        voxel_dim: dimension of the voxel for each axis (z, y, x)
        threshold: minimum value of the peaks to consider, overrides the one in `p`

    Returns:
        An array containing triples representing the coordinates of the seeds
    """

    vz, vy, vx = voxel_dim
    fp = _ellipsoid(
        (
            p.split * (p.diameter_z_um / vz) / 2,
            p.split * (p.diameter_xy_um / vy) / 2,
            p.split * (p.diameter_xy_um / vx) / 2,
        )
    )

    thr = p.threshold if threshold is None else threshold
    peaks = (response == ndimage.maximum_filter(response, footprint=fp, mode="nearest")) & (response > thr)
    return np.argwhere(peaks)


def find_blobs(
    img: Image,
    p: BlobParams,
    voxel: tuple[float, float, float],
    intensity=None,
    frame: int = 0,
    offset=(0, 0, 0),
    return_labels: bool = False,
) -> tuple[pd.DataFrame, np.ndarray | None, np.ndarray]:
    """Detection su un volume preprocessato (Z, Y, X) in [0, 1].

    intensity: volume grezzo della stessa ROI per il centroide pesato (default: img).
    offset:    origine della ROI in voxel, per coordinate nel volume intero.
    Ritorna (df, labels o None, seeds_response) — l'ultimo serve all'istogramma dei
    candidati nella GUI.
    """

    smoothed, response = log_response(img, p, voxel)
    seeds = find_seeds(response, p, voxel)
    seed_resp = response[tuple(seeds.T)] if len(seeds) else np.array([])
    if len(seeds) == 0:
        return pd.DataFrame(columns=DET_COLUMNS), None, seed_resp

    # della risposta LoG servono solo i valori ai semi: liberarla PRIMA del watershed
    # toglie 100 MB dal picco (e' il picco a limitare quanti processi puo' usare il batch)
    del response
    markers = np.zeros(img.shape, dtype=np.int32)
    markers[tuple(seeds.T)] = np.arange(1, len(seeds) + 1)
    seed_val = smoothed[tuple(seeds.T)]
    mask = smoothed > p.grow_frac * float(seed_val.min())
    labels = watershed(-smoothed, markers, mask=mask)
    del markers, mask

    # confine relativo: ogni regione tiene i voxel sopra grow_frac x il proprio picco
    n_lab = len(seeds) + 1
    peak = _label_max(labels, smoothed, n_lab)
    labels[smoothed < p.grow_frac * peak[labels]] = 0

    inten = img if intensity is None else intensity
    st = _label_stats(labels, inten, n_lab)
    idx = np.nonzero(st["n"])[0]
    idx = idx[idx > 0]
    if len(idx) == 0:
        return pd.DataFrame(columns=DET_COLUMNS), (labels if return_labels else None), seed_resp

    vox_vol = float(np.prod(voxel))
    df = pd.DataFrame(
        {
            "frame": frame,
            "label": idx,
            "z": st["z"][idx] + offset[0],
            "y": st["y"][idx] + offset[1],
            "x": st["x"][idx] + offset[2],
            "volume_um3": st["n"][idx] * vox_vol,
            "n_voxels": st["n"][idx],
            "z_extent": st["z_extent"][idx],
            "response": seed_resp[idx - 1],
            "peak": peak[idx],
            "mean_intensity": st["mean"][idx],
            "max_intensity": st["max"][idx],
        }
    )
    df["z_um"], df["y_um"], df["x_um"] = df["z"] * voxel[0], df["y"] * voxel[1], df["x"] * voxel[2]
    ok = (df["volume_um3"] >= p.min_volume_um3) & (df["volume_um3"] <= p.max_volume_um3)
    if return_labels:
        labels[np.isin(labels, df.loc[~ok, "label"].values)] = 0
    return df.loc[ok, DET_COLUMNS].reset_index(drop=True), (labels if return_labels else None), seed_resp
