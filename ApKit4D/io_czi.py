"""
io_czi.py
=========
Lettura lazy dei .czi lightfield gia' ricostruiti (Lightfield 4D Processing):
un volume (Z, Y, X) alla volta, mai l'intero (T, Z, Y, X) in memoria o su disco.
Un volume 95x512x512 uint16 si legge in ~0.1 s, quindi non serve alcuna cache:
la vecchia app scriveva l'intero stack in un memmap (118 GB per Exp-571).

Recuperato da app_prototipo/classic_tp/pipeline_step1_preprocess.py:
lettura voxel size, controllo sull'asse H (lightfield grezzo non ricostruito),
suggerimento automatico del range Z utile.
"""

import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np


@dataclass
class CziInfo:
    path: str
    n_t: int
    n_z: int
    n_y: int
    n_x: int
    n_c: int
    dtype: str
    px_x: float          # µm
    px_y: float          # µm
    px_z: float          # µm
    dt_s: Optional[float]
    dt_source: str

    @property
    def voxel(self):
        """Dimensione del voxel (z, y, x) in µm."""
        return (self.px_z, self.px_y, self.px_x)


def _parse_iso(s: str) -> datetime:
    # Zeiss scrive 7 cifre di frazione di secondo: Python ne accetta al massimo 6
    s = s.strip().rstrip("Z")
    if "." in s:
        head, frac = s.split(".")
        s = f"{head}.{frac[:6]}"
    return datetime.fromisoformat(s)


class CziSource:
    """Accesso per-volume a un .czi. Thread-safe: la lettura e' serializzata da un lock,
    cosi' la GUI puo' leggere dal thread di lavoro mentre napari legge per il cursore T."""

    def __init__(self, path, channel: int = 0):
        from aicspylibczi import CziFile

        self.path = Path(path)
        self.channel = channel
        self._czi = CziFile(str(self.path))
        self._lock = threading.Lock()
        dims = self._czi.get_dims_shape()[0]
        self._dims = dims

        if "Z" not in dims:
            if "H" in dims:
                raise RuntimeError(
                    f"'{self.path.name}' ha un asse H ({dims['H'][1]} elementi) e nessun asse Z: "
                    "e' un'acquisizione lightfield grezza, non ancora ricostruita. Va prima "
                    "passata in 'Lightfield 4D Processing' di ZEN per ottenere uno stack Z in µm.")
            raise RuntimeError(f"'{self.path.name}' non ha un asse Z (assi: {list(dims)})")

        px = self._read_voxel_size()
        dt, dt_src = self._read_dt(dims.get("T", (0, 1))[1])
        self.info = CziInfo(
            path=str(self.path),
            n_t=dims["T"][1] if "T" in dims else 1,
            n_z=dims["Z"][1], n_y=dims["Y"][1], n_x=dims["X"][1],
            n_c=dims["C"][1] if "C" in dims else 1,
            dtype=str(self.read(0).dtype),
            px_x=px["X"], px_y=px["Y"], px_z=px["Z"],
            dt_s=dt, dt_source=dt_src,
        )

    # ------------------------------------------------------------------ metadati
    def _raw_metadata(self) -> dict:
        from pylibCZIrw import czi as pyczi
        with pyczi.open_czi(str(self.path)) as doc:
            return doc.metadata["ImageDocument"]["Metadata"]

    def _read_voxel_size(self) -> dict:
        px = {"X": np.nan, "Y": np.nan, "Z": np.nan}
        try:
            for ax in self._raw_metadata()["Scaling"]["Items"]["Distance"]:
                if ax.get("@Id") in px:
                    px[ax["@Id"]] = float(ax["Value"]) * 1e6
        except Exception as e:  # metadati illeggibili: meglio fallire in modo esplicito
            raise RuntimeError(f"voxel size non leggibile da {self.path.name}: {e}") from e
        if not np.isfinite(px["Z"]):
            raise RuntimeError(f"{self.path.name}: manca la scala Z nei metadati")
        return px

    def _read_dt(self, n_t: int):
        """Passo temporale in s. Tre fonti, in ordine: intervallo fisso nei metadati,
        allegato TimeStamps, AcquisitionTime dei subblock (primo vs ultimo volume).
        Exp-583 dichiara l'allegato TimeStamps ma non lo contiene: da qui la terza via."""
        if n_t < 2:
            return None, "un solo frame"
        try:
            t = self._raw_metadata()["Information"]["Image"]["Dimensions"]["T"]
            inc = t.get("Positions", {}).get("Interval", {}).get("Increment")
            if inc is not None and float(inc) > 0:
                return float(inc), "metadati (T Increment)"
        except Exception:
            pass
        try:
            import czifile
            with czifile.CziFile(str(self.path)) as c:
                for a in c.attachments():
                    if a.attachment_entry.name == "TimeStamps":
                        ts = np.asarray(a.data(), dtype=float)
                        if len(ts) > 1:
                            return float(np.median(np.diff(ts))), "allegato TimeStamps"
        except Exception:
            pass
        try:
            def acq(t):
                s = self._czi.read_subblock_metadata(T=t, Z=0, C=self.channel)[0][1]
                return _parse_iso(re.search(r"<AcquisitionTime>([^<]+)", s).group(1))
            span = (acq(n_t - 1) - acq(0)).total_seconds()
            if span > 0:
                return span / (n_t - 1), "AcquisitionTime dei volumi"
        except Exception:
            pass
        return None, "non trovato"

    # ------------------------------------------------------------------ dati
    def read(self, t: int) -> np.ndarray:
        """Volume (Z, Y, X) al frame t, dtype nativo (tipicamente uint16)."""
        kw = {}
        if "T" in self._dims:
            kw["T"] = int(t)
        if "C" in self._dims:
            kw["C"] = self.channel
        with self._lock:
            vol, _ = self._czi.read_image(**kw)
        return vol.reshape(vol.shape[-3:])

    def as_dask(self):
        """Array lazy (T, Z, Y, X): napari legge solo il volume del frame mostrato."""
        import dask
        import dask.array as da

        i = self.info
        shape = (i.n_z, i.n_y, i.n_x)
        frames = [da.from_delayed(dask.delayed(self.read)(t), shape=shape, dtype=i.dtype)
                  for t in range(i.n_t)]
        return da.stack(frames)


# ----------------------------------------------------------------------------
def suggest_z_range(vol: np.ndarray):
    """Range Z utile da un solo volume: taglia le slice di puro rumore ai bordi.

    Stessa euristica del vecchio _auto_crop_z (profilo p99 per slice, soglia 1.5x il
    p20 del profilo in basso, gradiente in alto), ma su un volume solo: il vecchio
    faceva la mediana su tutti i frame, cioe' leggeva l'intero file.
    """
    n_z = vol.shape[0]
    profile = np.percentile(vol.reshape(n_z, -1), 99, axis=1)
    thr = np.percentile(profile, 20) * 1.5
    above = np.where(profile > thr)[0]
    z_min = max(0, int(above[0]) - 1) if len(above) else 0
    grad = np.gradient(profile)
    g_thr = np.percentile(grad, 90)
    z_max = n_z - 1
    for z in range(n_z - 1, n_z // 2, -1):
        if grad[z] < g_thr:
            z_max = z
            break
    if z_min >= z_max:
        z_min, z_max = 0, n_z - 1
    return z_min, z_max, profile
