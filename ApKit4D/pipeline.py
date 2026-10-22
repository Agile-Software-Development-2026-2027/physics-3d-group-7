"""
pipeline.py
===========
Una pipeline e' un file json che descrive tutta l'analisi di un esperimento: quale .czi,
quale ROI, quale intervallo di frame, i parametri di preprocessing, del blob finder e del
linking. Si salva, si rilancia, si passa a qualcun altro.

Serve a due cose: non rifare i passaggi a mano ogni volta, e poter dire esattamente con
quali impostazioni e' stato prodotto un certo risultato — il file viene copiato accanto
agli output.

    python -m ApKit4D.pipeline --elenco
    python -m ApKit4D.pipeline pipelines/571_centro.json
    python -m ApKit4D.pipeline pipelines/571_centro.json --solo linking

Le pipeline stanno in `pipelines/` nella cartella del progetto. Dalla GUI si salvano con
il pannello "7 · Pipeline", che ci mette dentro i parametri correnti.
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

from ApKit4D import params as P
from ApKit4D.blobfinder import BlobParams
from ApKit4D.io_table import find_table
from ApKit4D.preprocess import PreprocParams

CARTELLA = P.BASE_DIR / "pipelines"
VERSIONE = 1
PASSI = ("detection", "linking")


def percorso(nome) -> Path:
    """Accetta sia un nome ('571_centro') sia un percorso completo."""
    p = Path(nome)
    if p.suffix == ".json" and (p.is_absolute() or p.exists()):
        return p
    return CARTELLA / f"{Path(nome).stem}.json"


def elenco():
    return sorted(CARTELLA.glob("*.json")) if CARTELLA.is_dir() else []


def salva(nome, czi, channel, pp: PreprocParams, bp: BlobParams, t0, t1, out_dir,
          formato="parquet", workers=16, link=None, etichetta="", note=""):
    """Scrive la pipeline su disco e ne ritorna il percorso."""
    dati = {
        "versione": VERSIONE,
        "nome": Path(nome).stem,
        "creata": datetime.now().isoformat(timespec="seconds"),
        "note": note,
        "czi": str(czi),
        "channel": int(channel),
        "t0": int(t0), "t1": int(t1),
        "out": str(out_dir),
        "formato": formato,
        "workers": int(workers),
        "etichetta": etichetta,
        "preproc": pp.to_dict(),
        "blob": bp.to_dict(),
        "link": link or {"min_len": 5, "max_speed": 250.0, "max_gap": 3, "ritaglio": True},
    }
    CARTELLA.mkdir(parents=True, exist_ok=True)
    p = percorso(nome)
    p.write_text(json.dumps(dati, indent=2))
    return p


def carica(nome) -> dict:
    p = percorso(nome)
    if not p.is_file():
        raise FileNotFoundError(f"pipeline non trovata: {p}")
    d = json.loads(p.read_text())
    if d.get("versione") != VERSIONE:
        raise ValueError(f"{p.name}: versione {d.get('versione')} non supportata "
                         f"(questa app usa la {VERSIONE})")
    return d


def roi_um_da_pipeline(d: dict):
    """ROI in µm per il ritaglio del linking, dalla ROI in voxel del preprocessing."""
    from ApKit4D.io_czi import CziSource
    from ApKit4D.preprocess import roi_slices
    i = CziSource(d["czi"], d.get("channel", 0)).info
    pp = PreprocParams.from_dict(d["preproc"])
    sz, sy, sx = roi_slices(pp, (i.n_z, i.n_y, i.n_x))
    vz, vy, vx = i.voxel
    return [sz.start * vz, (sz.stop - 1) * vz, sy.start * vy, (sy.stop - 1) * vy,
            sx.start * vx, (sx.stop - 1) * vx]


def esegui(d: dict, solo=None, stampa=print):
    """Esegue la pipeline. `solo` limita a un passo ('detection' o 'linking')."""
    from ApKit4D import batch, link

    passi = [solo] if solo else list(PASSI)
    out = Path(d["out"])
    out.mkdir(parents=True, exist_ok=True)
    stem = P.stem_of(d["czi"])
    prodotti = {}
    t_inizio = time.time()
    stampa(f"=== pipeline '{d.get('nome', '?')}' — {Path(d['czi']).name} ===")

    if "detection" in passi:
        stampa(f"\n--- detection: frame {d['t0']}-{d['t1']} ---")
        prodotti["blobs"] = batch.run(
            d["czi"], d.get("channel", 0), PreprocParams.from_dict(d["preproc"]),
            BlobParams.from_dict(d["blob"]), d["t0"], d["t1"], out,
            workers=d.get("workers", 16), fmt=d.get("formato", "parquet"))

    if "linking" in passi:
        blobs = prodotti.get("blobs") or find_table(out, stem, "blobs")
        if blobs is None:
            raise FileNotFoundError(
                f"nessuna tabella di blob per {stem} in {out}: esegui prima la detection")
        L = d.get("link", {})
        ritaglio = L.get("ritaglio", True)
        stampa(f"\n--- linking su {Path(blobs).name} ---")
        prodotti.update(link.esegui_su_file(
            blobs, out, max_speed=L.get("max_speed", 250.0), max_gap=L.get("max_gap", 3),
            min_len=L.get("min_len", 5),
            t0=d["t0"] if ritaglio else None, t1=d["t1"] if ritaglio else None,
            roi_um=roi_um_da_pipeline(d) if ritaglio else None,
            etichetta=d.get("etichetta", ""), fmt=d.get("formato", "parquet"), stampa=stampa))

    # la pipeline usata resta accanto ai risultati: cosi' si sa sempre come sono nati
    copia = out / f"{stem}{('_' + d['etichetta']) if d.get('etichetta') else ''}_pipeline.json"
    copia.write_text(json.dumps(d, indent=2))
    prodotti["pipeline"] = copia
    stampa(f"\n=== fatta in {time.time() - t_inizio:.0f} s ===")
    for k, v in prodotti.items():
        stampa(f"  {k:12s} {v}")
    return prodotti


def main():
    ap = argparse.ArgumentParser(description="ApKit4D — esegue una pipeline salvata")
    ap.add_argument("pipeline", nargs="?", help="nome o percorso del file json")
    ap.add_argument("--elenco", action="store_true", help="elenca le pipeline salvate")
    ap.add_argument("--solo", choices=PASSI, default=None, help="esegue un solo passo")
    a = ap.parse_args()

    if a.elenco or not a.pipeline:
        trovate = elenco()
        if not trovate:
            print(f"nessuna pipeline in {CARTELLA}")
        for p in trovate:
            d = json.loads(p.read_text())
            print(f"  {p.stem:28s} {Path(d.get('czi', '?')).name}  "
                  f"frame {d.get('t0')}-{d.get('t1')}  {d.get('note', '')}")
        return

    try:
        esegui(carica(a.pipeline), a.solo)
    except (FileNotFoundError, ValueError) as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
