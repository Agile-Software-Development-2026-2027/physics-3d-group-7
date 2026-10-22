"""
batch.py
========
Preprocessing + blob finder su un intervallo di frame, in parallelo, senza GUI.
La GUI lo lancia come processo separato con i parametri correnti; si puo' usare
anche da terminale:

    python -m ApKit4D.batch "data/raw/Experiment-583-Lightfield 4D Processing.czi" \\
        --t0 0 --t1 599 --workers 32
    python -m ApKit4D.batch <file.czi> --params mio_set.json --out /media/user/LaCie/lf

Senza --params usa quelli salvati per quel file in data/app_params.json.

Output in --out (default data/processed/):
    <stem>_blobs.csv          una riga per blob: frame, t_s, z/y/x (voxel e µm), volume, ...
    <stem>_blobs_params.json  parametri, metadati del file e intervallo usati
"""

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from ApKit4D import params as P
from ApKit4D.blobfinder import BlobParams, find_blobs, DET_COLUMNS
from ApKit4D.io_table import FORMATS, TableWriter, table_path
from ApKit4D.io_czi import CziSource
from ApKit4D.preprocess import PreprocParams, preprocess, roi_slices, roi_offset


def detect_frame(src: CziSource, t: int, pp: PreprocParams, bp: BlobParams) -> pd.DataFrame:
    """Un frame: lettura -> ROI -> preprocessing -> blob. Usata anche dalla GUI."""
    vol = src.read(t)
    sl = roi_slices(pp, vol.shape)
    img = preprocess(vol[sl], pp, src.info.voxel)
    df, _, _ = find_blobs(img, bp, src.info.voxel, intensity=vol[sl], frame=t,
                          offset=roi_offset(pp, vol.shape))
    return df


def _work(czi, channel, pp_d, bp_d, frames):
    # un CziSource per task: gli handle aicspylibczi non si passano fra processi
    src = CziSource(czi, channel)
    pp, bp = PreprocParams.from_dict(pp_d), BlobParams.from_dict(bp_d)
    return [detect_frame(src, t, pp, bp) for t in frames]


# picco di memoria misurato per processo su un volume 95x512x512 (Exp-571): ~1.1 GB
RAM_PER_WORKER_GB = 1.2


def cap_workers(requested: int, per_worker_gb: float = RAM_PER_WORKER_GB):
    """Limita i processi alla RAM libera: ogni worker tiene in memoria il volume e alcune
    copie float32 (~1.1 GB al picco). Ritorna (workers, motivo)."""
    try:
        import psutil
        avail_gb = psutil.virtual_memory().available / 1e9
    except Exception:
        return requested, ""
    cap = max(1, int(0.6 * avail_gb / per_worker_gb))
    if requested <= cap:
        return requested, f"{avail_gb:.0f} GB liberi, ~{requested * per_worker_gb:.0f} GB stimati"
    return cap, (f"ridotti da {requested} a {cap}: {avail_gb:.0f} GB liberi, "
                 f"~{per_worker_gb:.1f} GB per processo")


def run(czi, channel, pp: PreprocParams, bp: BlobParams, t0, t1, out_dir: Path,
        workers=16, chunk=10, fmt="parquet"):
    src = CziSource(czi, channel)
    info = src.info
    t1 = min(t1, info.n_t - 1)
    frames = list(range(t0, t1 + 1))
    chunks = [frames[i:i + chunk] for i in range(0, len(frames), chunk)]
    workers, why = cap_workers(workers)
    print(f"{Path(czi).name}: frame {t0}-{t1} ({len(frames)}), {len(chunks)} blocchi, "
          f"{workers} processi" + (f" ({why})" if why else ""), flush=True)

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = P.stem_of(czi)
    out_path = table_path(out_dir, stem, "blobs", fmt)
    writer = TableWriter(out_path)

    t_start = time.time()
    done = 0
    with ProcessPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(_work, czi, channel, pp.to_dict(), bp.to_dict(), c) for c in chunks]
        for f in as_completed(futs):
            res = f.result()
            # scritto subito: tenere tutti i frame fino alla fine costava ~700 MB su Exp-571,
            # e un'interruzione avrebbe buttato via tutto
            for d in res:
                if len(d):
                    d = d.copy()
                    d.insert(1, "t_s", d["frame"] * info.dt_s if info.dt_s else np.nan)
                    writer.append(d)
            done += len(res)
            el = time.time() - t_start
            print(f"  {done}/{len(frames)} frame  ({el:.0f} s, ~{el / done * (len(frames) - done):.0f} s rimanenti)",
                  flush=True)
    writer.close()

    n = writer.n_rows
    meta = {"czi": str(czi), "channel": channel, "t0": t0, "t1": t1,
            "created": datetime.now().isoformat(timespec="seconds"),
            "info": info.__dict__, "preproc": pp.to_dict(), "blob": bp.to_dict(),
            "n_blobs": int(n), "formato": fmt,
            "ordinato_per_frame": False,   # i blocchi arrivano fuori ordine: ordina chi legge
            "blobs_per_frame_mean": float(n / max(1, len(frames)))}
    (out_dir / f"{stem}_blobs_params.json").write_text(json.dumps(meta, indent=2))
    print(f"Fatto: {n} blob, {n / max(1, len(frames)):.1f} per frame -> {out_path}", flush=True)
    return out_path


def main():
    ap = argparse.ArgumentParser(description="ApKit4D — blob finder batch su un .czi lightfield")
    ap.add_argument("czi", type=Path)
    ap.add_argument("--params", type=Path, default=None,
                    help="json con chiavi preproc/blob/channel (default: data/app_params.json)")
    ap.add_argument("--t0", type=int, default=None)
    ap.add_argument("--t1", type=int, default=None)
    ap.add_argument("--out", type=Path, default=P.DATA_OUT)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--chunk", type=int, default=10, help="frame per task")
    ap.add_argument("--format", choices=FORMATS, default="parquet",
                    help="parquet (default, ~5x piu' piccolo e 20x piu' veloce da leggere) o csv")
    a = ap.parse_args()

    entry = json.loads(a.params.read_text()) if a.params else P.load(P.stem_of(a.czi))
    if not entry:
        sys.exit(f"Nessun parametro salvato per {a.czi.name}: aprilo prima nella GUI o passa --params")
    t0 = a.t0 if a.t0 is not None else entry.get("t0", 0)
    t1 = a.t1 if a.t1 is not None else entry.get("t1", 10 ** 9)
    run(a.czi, entry.get("channel", 0), PreprocParams.from_dict(entry.get("preproc")),
        BlobParams.from_dict(entry.get("blob")), t0, t1, a.out, a.workers, a.chunk, a.format)


if __name__ == "__main__":
    main()
