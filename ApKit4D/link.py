"""
link.py
=======
Tracking dei blob in traiettorie, schema LAP (Jaqaman et al. 2008) in due passi:

  1. frame-to-frame: ogni traccia attiva viene messa in corrispondenza con le detection
     del frame successivo risolvendo un'assegnazione 1-1 di costo minimo. Il costo e' la
     distanza al quadrato dalla posizione PREVISTA, non dall'ultima osservata: le alghe
     nuotano in modo persistente (α ≈ 1.5-1.7 dalle MSD), quindi la velocita' corrente e'
     un buon predittore e l'errore di predizione resta molto sotto la distanza tipica fra
     cellule vicine (~49 µm di mediana nei dati a 20 vol/s).
  2. chiusura dei buchi: i segmenti di traccia rimasti spezzati da detection mancanti
     vengono ricollegati con un secondo LAP su salti fino a `max_gap` frame, con costo
     basato sulla continuita' di velocita'.

Perche' non un vicino piu' prossimo: con detection mancanti o due cellule vicine il
greedy sceglie il primo che capita e produce scambi; l'assegnazione globale sceglie la
combinazione di costo minimo su tutto il frame.

Perche' il gating conta: nei dati reali il vicino piu' prossimo sta a ~49 µm, mentre in
0.0505 s una cellula a 100-200 µm/s percorre 5-10 µm. Con un raggio di 15-20 µm i
candidati sono in media 0.1 per blob, cioe' il problema e' quasi privo di ambiguita';
a 144 µm i candidati diventano ~10 e gli scambi fra cellule sono inevitabili.

Uso:
    python -m ApKit4D.link data/processed/<stem>_blobs.csv
    python -m ApKit4D.link <blobs.csv> --max-dist 15 --max-gap 3 --min-len 5
"""

import argparse
import json
import sys
from dataclasses import asdict, dataclass, fields
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

from ApKit4D.io_table import FORMATS, read_table, table_path


def filtri_ritaglio(t0=None, t1=None, roi_um=None):
    """Filtri di lettura da un ritaglio: (t0, t1) in frame, roi_um = z0,z1,y0,y1,x0,x1 in µm."""
    f = []
    if t0 is not None:
        f.append(("frame", ">=", int(t0)))
    if t1 is not None:
        f.append(("frame", "<=", int(t1)))
    if roi_um:
        for asse, (lo, hi) in zip(("z_um", "y_um", "x_um"),
                                  [roi_um[0:2], roi_um[2:4], roi_um[4:6]]):
            f.append((asse, ">=", float(lo)))
            f.append((asse, "<=", float(hi)))
    return f

BIG = 1e12
POS = ["z_um", "y_um", "x_um"]


def gate_from_dt(dt_s, max_speed_um_s=250.0):
    """Raggio di ricerca da velocita' massima attesa x dt. Chlamydomonas nuota a 100-200 µm/s,
    quindi 250 µm/s e' un tetto con margine: a 10 vol/s da' 25 µm, a 20 vol/s 12.6 µm.
    Un gate fisso non va bene per entrambi i regimi."""
    return float(max_speed_um_s * dt_s)


@dataclass
class LinkParams:
    max_dist_um: float = 20.0      # gating frame-to-frame (raggio di ricerca)
    max_gap: int = 3               # frame mancanti colmabili nella chiusura dei buchi
    gap_dist_um: float = 25.0      # gating della chiusura, per frame di salto
    min_len: int = 3               # punti minimi per tenere una traccia
    vel_smooth: float = 0.5        # peso della nuova velocita' nella stima (0 = ferma)
    n_ricampioni: int = 20         # per l'affidabilita' di ogni collegamento (0 = non calcolarla)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        names = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in (d or {}).items() if k in names})


# ---------------------------------------------------------------------------
def solve_lap(rows, cols, costs, n_a, n_b):
    """Assegnazione 1-1 di costo minimo sui soli candidati (rows, cols).

    La matrice completa n_a x n_b sarebbe enorme e inutile: quasi tutte le coppie sono
    fuori dal gating. Il grafo bipartito dei candidati viene spezzato nelle sue componenti
    connesse e ogni componente risolta a parte con linear_sum_assignment — le componenti
    sono piccole finche' il gating e' stretto.
    Ritorna un array (k, 2) di coppie (indice_a, indice_b).
    """
    if len(rows) == 0:
        return np.empty((0, 2), dtype=int)
    g = coo_matrix((np.ones(len(rows)), (rows, cols + n_a)), shape=(n_a + n_b, n_a + n_b))
    n_comp, lab = connected_components(g + g.T, directed=False)

    out = []
    comp_of_edge = lab[rows]
    order = np.argsort(comp_of_edge, kind="stable")
    rows, cols, costs, comp_of_edge = (a[order] for a in (rows, cols, costs, comp_of_edge))
    starts = np.searchsorted(comp_of_edge, np.unique(comp_of_edge))
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(rows)
        r, c, w = rows[s:e], cols[s:e], costs[s:e]
        ur, ir = np.unique(r, return_inverse=True)
        uc, ic = np.unique(c, return_inverse=True)
        if len(ur) == 1 and len(uc) == 1:          # caso banale: nessuna ambiguita'
            out.append((ur[0], uc[0]))
            continue
        m = np.full((len(ur), len(uc)), BIG)
        m[ir, ic] = w
        ri, ci = linear_sum_assignment(m)
        for a, b in zip(ri, ci):
            if m[a, b] < BIG:
                out.append((ur[a], uc[b]))
    return np.array(out, dtype=int) if out else np.empty((0, 2), dtype=int)


# ---------------------------------------------------------------------------
def link_frame_to_frame(det: pd.DataFrame, p: LinkParams, seme=0):
    """Passo 1. Ritorna (etichette, affidabilita'), una voce per riga di `det`.

    L'affidabilita' di un collegamento e' calcolata come in u-track3D (Cell Rep Methods
    2023): si ricampiona N volte la posizione PREVISTA di ogni traccia e si rifa'
    l'assegnazione; il punteggio e' la frazione di ricampionamenti in cui il collegamento
    resta lo stesso. 1 = nessuna ambiguita', 0 = l'esito dipende interamente dalla
    previsione.

    La dispersione del ricampionamento non e' un valore scelto a priori ma viene stimata
    dai residui veri (posizione osservata meno prevista) dei collegamenti accettati nei
    frame gia' elaborati, asse per asse. Questo e' il punto: il punteggio non presuppone
    che il modello di moto sia quello giusto per il campione. Se non lo e', i residui sono
    grandi, le perturbazioni pure, e i punteggi scendono — cioe' il metodo segnala da solo
    che la previsione non e' affidabile su quei dati.
    """
    det = det.reset_index(drop=True)
    labels = np.full(len(det), -1, dtype=int)
    stabilita = np.full(len(det), np.nan)
    margine = np.full(len(det), np.nan)       # quanto la seconda scelta era piu' lontana, in sigma
    n_cand = np.zeros(len(det), dtype=np.int16)
    frames = np.sort(det["frame"].unique())
    by_frame = {f: g.index.to_numpy() for f, g in det.groupby("frame")}
    xyz = det[POS].to_numpy()
    rng = np.random.default_rng(seme)

    act_lab, act_pos, act_vel = [], [], []
    n_tracks = 0
    gate2 = p.max_dist_um ** 2
    # dispersione iniziale: un terzo del raggio di ricerca, poi la rimpiazzano i dati
    sigma = np.full(3, p.max_dist_um / 3)

    for f in frames:
        idx = by_frame[f]
        cur = xyz[idx]
        pairs = np.empty((0, 2), dtype=int)
        if act_lab:
            pred = np.array(act_pos) + np.array(act_vel)
            tree = cKDTree(cur)
            cand = tree.query_ball_point(pred, p.max_dist_um)
            rows = np.concatenate([np.full(len(c), i) for i, c in enumerate(cand) if c]) \
                if any(cand) else np.empty(0, dtype=int)
            cols = np.concatenate([np.asarray(c) for c in cand if c]) \
                if any(cand) else np.empty(0, dtype=int)
            costs = ((pred[rows] - cur[cols]) ** 2).sum(axis=1) if len(rows) else np.empty(0)
            tieni = costs <= gate2
            rows, cols, costs = rows[tieni].astype(int), cols[tieni].astype(int), costs[tieni]
            pairs = solve_lap(rows, cols, costs, len(act_lab), len(cur))

            if p.n_ricampioni and len(pairs):
                conteggio = {(int(a), int(b)): 0 for a, b in pairs}
                for _ in range(p.n_ricampioni):
                    # si perturba la previsione, non la detection: l'incertezza sta li'
                    scosso = pred + rng.normal(0.0, sigma, size=pred.shape)
                    c_p = ((scosso[rows] - cur[cols]) ** 2).sum(axis=1)
                    for a, b in solve_lap(rows, cols, c_p, len(act_lab), len(cur)):
                        chiave = (int(a), int(b))
                        if chiave in conteggio:
                            conteggio[chiave] += 1
                for a, b in pairs:
                    stabilita[idx[b]] = conteggio[(int(a), int(b))] / p.n_ricampioni

            if len(pairs):
                # Margine: distanza della migliore ALTERNATIVA meno quella scelta, in unita'
                # di sigma della previsione. Serve perche' il punteggio Monte Carlo satura
                # quando le alternative sono lontane: li' dice solo "nessuna ambiguita'",
                # mentre il margine continua a distinguere un caso comodo da uno al limite.
                # Si guardano entrambi i lati: altre detection per quella traccia, e altre
                # tracce che reclamano quella detection.
                sigma_eff = float(np.sqrt(np.mean(sigma ** 2)))
                d_edge = np.sqrt(((pred[rows] - cur[cols]) ** 2).sum(axis=1))
                scelta = {(int(a), int(b)): True for a, b in pairs}
                best_per_traccia, best_per_det = {}, {}
                for e, (ia, ib) in enumerate(zip(rows, cols)):
                    if (int(ia), int(ib)) in scelta:
                        continue
                    best_per_traccia[int(ia)] = min(best_per_traccia.get(int(ia), np.inf), d_edge[e])
                    best_per_det[int(ib)] = min(best_per_det.get(int(ib), np.inf), d_edge[e])
                scelte_d = {(int(a), int(b)): np.linalg.norm(pred[a] - cur[b]) for a, b in pairs}
                for a, b in pairs:
                    a, b = int(a), int(b)
                    alt = min(best_per_traccia.get(a, np.inf), best_per_det.get(b, np.inf))
                    margine[idx[b]] = ((alt - scelte_d[(a, b)]) / sigma_eff
                                       if np.isfinite(alt) else np.inf)
                    n_cand[idx[b]] = int((rows == a).sum())

            if len(pairs):
                # residui: quanto la previsione ha sbagliato davvero su questo frame
                res = np.abs(cur[pairs[:, 1]] - pred[pairs[:, 0]])
                nuova_sigma = 1.4826 * np.median(res, axis=0)      # robusta agli estremi
                nuova_sigma = np.maximum(nuova_sigma, 1e-3)
                sigma = 0.8 * sigma + 0.2 * nuova_sigma

        # Le liste vengono ricostruite da zero a ogni frame: restano attive solo le tracce
        # che hanno una detection in QUESTO frame (proseguite o appena nate). Quelle rimaste
        # senza corrispondenza si chiudono qui; a ricucirle, se e' solo una detection
        # mancante, pensa la chiusura dei buchi.
        next_lab, next_pos, next_vel = [], [], []
        matched_dets = set(pairs[:, 1].tolist())
        for a, b in pairs:
            new_pos = cur[b]
            vel = new_pos - act_pos[a]
            next_lab.append(act_lab[a])
            next_pos.append(new_pos)
            next_vel.append((1 - p.vel_smooth) * np.asarray(act_vel[a]) + p.vel_smooth * vel)
            labels[idx[b]] = act_lab[a]

        for b in range(len(cur)):
            if b in matched_dets:
                continue
            labels[idx[b]] = n_tracks
            next_lab.append(n_tracks)
            next_pos.append(cur[b])
            next_vel.append(np.zeros(3))
            n_tracks += 1

        act_lab, act_pos, act_vel = next_lab, next_pos, next_vel

    return labels, stabilita, margine, n_cand


# ---------------------------------------------------------------------------
def close_gaps(det: pd.DataFrame, labels: np.ndarray, p: LinkParams):
    """Passo 2: ricollega la fine di un segmento con l'inizio di un altro entro `max_gap`
    frame, se la posizione iniziale del secondo e' compatibile con la velocita' del primo."""
    if p.max_gap < 1:
        return labels
    df = det.assign(_lab=labels)
    g = df.groupby("_lab")
    first = g.first()
    last = g.last()
    labs = last.index.to_numpy()
    lengths = g.size().to_numpy()

    end_pos = last[POS].to_numpy()
    end_frame = last["frame"].to_numpy()
    start_pos = first[POS].to_numpy()
    start_frame = first["frame"].to_numpy()

    # velocita' a fine segmento, dagli ultimi 3 punti (una sola passata, non una per traccia)
    tail = df.groupby("_lab").tail(3).groupby("_lab")
    dpos = tail[POS].last() - tail[POS].first()
    dfr = np.maximum(1, (tail["frame"].last() - tail["frame"].first()).to_numpy())
    vel = (dpos.to_numpy() / dfr[:, None])
    vel = np.where((lengths >= 2)[:, None], vel, 0.0)

    rows, cols, costs = [], [], []
    tree = cKDTree(start_pos)
    for gap in range(1, p.max_gap + 2):              # gap=1 => frame consecutivi
        pred = end_pos + vel * gap
        cand = tree.query_ball_point(pred, p.gap_dist_um * gap)
        for i, js in enumerate(cand):
            for j in js:
                if start_frame[j] - end_frame[i] != gap:
                    continue
                rows.append(i)
                cols.append(j)
                costs.append(float(((pred[i] - start_pos[j]) ** 2).sum()))
    pairs = solve_lap(np.array(rows, dtype=int), np.array(cols, dtype=int),
                      np.array(costs), len(labs), len(labs))

    # unione dei segmenti collegati (catene: A->B->C)
    parent = {lab: lab for lab in labs}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for i, j in pairs:
        parent[find(labs[j])] = find(labs[i])
    return np.array([find(l) for l in labels])


# ---------------------------------------------------------------------------
def run_link(det: pd.DataFrame, p: LinkParams):
    """Detection -> traiettorie. Ritorna (tracks, stats)."""
    det = det.sort_values(["frame"]).reset_index(drop=True)
    lab1, stabilita, margine, n_cand = link_frame_to_frame(det, p)
    det = det.assign(affidabilita=stabilita, margine_sigma=margine, n_candidati=n_cand)
    n1 = len(np.unique(lab1))
    lab2 = close_gaps(det, lab1, p)
    n2 = len(np.unique(lab2))

    tracks = det.assign(particle=lab2)
    size = tracks.groupby("particle")["frame"].size()
    tracks = tracks[tracks["particle"].isin(size[size >= p.min_len].index)].copy()
    # etichette compatte e ordinate per primo frame
    order = tracks.groupby("particle")["frame"].min().sort_values().index
    tracks["particle"] = tracks["particle"].map({old: i for i, old in enumerate(order)})
    tracks = tracks.sort_values(["particle", "frame"]).reset_index(drop=True)

    stats = track_stats(tracks)
    info = {"n_detections": len(det), "n_segmenti_passo1": int(n1),
            "n_tracce_dopo_chiusura": int(n2), "n_tracce_tenute": int(tracks["particle"].nunique()),
            "buchi_colmati": int(n1 - n2)}
    return tracks, stats, info


def track_stats(tracks: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for pid, g in tracks.groupby("particle"):
        xyz = g[POS].to_numpy()
        fr = g["frame"].to_numpy()
        d = np.diff(xyz, axis=0)
        dt_fr = np.diff(fr)
        step = np.linalg.norm(d, axis=1)
        dt_s = g["t_s"].to_numpy() if "t_s" in g else None
        dur = (dt_s[-1] - dt_s[0]) if dt_s is not None and np.isfinite(dt_s).all() else np.nan
        # angolo fra passi successivi: uno scambio fra due cellule produce inversioni (~180°)
        ang = np.array([])
        if len(d) >= 2:
            u = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
            cos = np.clip((u[:-1] * u[1:]).sum(axis=1), -1, 1)
            ang = np.degrees(np.arccos(cos))
        aff = g["affidabilita"].to_numpy() if "affidabilita" in g else np.array([np.nan])
        aff = aff[np.isfinite(aff)]
        marg = g["margine_sigma"].to_numpy() if "margine_sigma" in g else np.array([np.nan])
        marg = marg[np.isfinite(marg)]
        cand = g["n_candidati"].to_numpy() if "n_candidati" in g else np.array([0])
        rows.append({"particle": pid, "n_points": len(g), "span_frames": int(fr[-1] - fr[0] + 1),
                     "affidabilita_media": float(np.mean(aff)) if len(aff) else np.nan,
                     "affidabilita_min": float(np.min(aff)) if len(aff) else np.nan,
                     "frac_passi_incerti": float((aff < 0.5).mean()) if len(aff) else np.nan,
                     "margine_min_sigma": float(np.min(marg)) if len(marg) else np.inf,
                     "frac_passi_contesi": float((cand > 1).mean()) if len(cand) else np.nan,
                     "n_gaps": int((dt_fr > 1).sum()), "duration_s": dur,
                     "net_displacement_um": float(np.linalg.norm(xyz[-1] - xyz[0])),
                     "path_length_um": float(step.sum()),
                     "median_step_um": float(np.median(step)) if len(step) else np.nan,
                     "median_turn_deg": float(np.median(ang)) if len(ang) else np.nan,
                     "frac_turn_gt_120": float((ang > 120).mean()) if len(ang) else np.nan})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
def direction_acf(tracks, max_lag=15, min_points=20):
    """<cos θ> fra le direzioni di nuoto a distanza `lag` frame, sulle tracce lunghe.

    Serve a due cose insieme: collegamenti casuali la schiacciano a zero, mentre il nuoto
    elicoidale della Chlamydomonas (~2 Hz di rotazione) la fa oscillare, con minimi a mezzo
    giro e massimi a giro intero. Sul file a 10 vol/s il periodo misurato e' 4 frame ≈ 0.4 s.
    """
    out = {l: [] for l in range(1, max_lag + 1)}
    for _, g in tracks.groupby("particle"):
        if len(g) < min_points:
            continue
        d = np.diff(g[POS].to_numpy(), axis=0)
        u = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
        for l in out:
            if len(u) > l:
                out[l].append((u[:-l] * u[l:]).sum(axis=1))
    lags = [l for l in out if out[l]]
    vals = [float(np.concatenate(out[l]).mean()) for l in lags]
    return np.array(lags), np.array(vals)


def make_diagnostics(tracks, stats, info, p: LinkParams, name, dt_s=None):
    fig, axes = plt.subplots(2, 3, figsize=(16, 8))
    fig.suptitle(f"{name} — linking LAP  (gate {p.max_dist_um:g} µm, gap ≤ {p.max_gap}, "
                 f"{info['n_tracce_tenute']} tracce)", fontsize=11)

    ax = axes[0, 0]
    ax.hist(stats["n_points"], bins=range(1, int(stats["n_points"].max()) + 2),
            color="#00838f")
    ax.set(xlabel="punti per traccia", ylabel="n. tracce", yscale="log",
           title=f"A — lunghezza delle tracce (mediana {stats['n_points'].median():.0f})")
    ax.grid(alpha=0.3)

    ax = axes[0, 1]
    per_frame = tracks.groupby("frame")["particle"].nunique()
    ax.plot(per_frame.index, per_frame.values, lw=1, color="#1e88e5")
    ax.set(xlabel="frame", ylabel="tracce attive", title="B — tracce attive per frame")
    ax.grid(alpha=0.3)

    ax = axes[1, 0]
    step = stats["median_step_um"].dropna()
    speed = step / dt_s if dt_s else step
    ax.hist(speed, bins=60, color="#8e24aa")
    ax.set(xlabel="velocita' mediana per traccia (µm/s)" if dt_s else "passo mediano (µm)",
           ylabel="n. tracce", title="C — velocita' di nuoto")
    ax.grid(alpha=0.3)

    ax = axes[0, 2]
    lags, acf = direction_acf(tracks)
    if len(lags):
        x = lags * dt_s if dt_s else lags
        ax.plot(x, acf, "o-", color="#43a047")
        ax.axhline(0, color="gray", lw=0.8)
    ax.set(xlabel="lag (s)" if dt_s else "lag (frame)", ylabel="⟨cos θ⟩",
           title="E — autocorrelazione della direzione\n(oscillazione = nuoto elicoidale)")
    ax.grid(alpha=0.3)

    ax = axes[1, 2]
    marg = stats["margine_min_sigma"].replace(np.inf, np.nan).dropna() if "margine_min_sigma" in stats else []
    if len(marg):
        ax.hist(np.clip(marg, 0, 40), bins=40, color="#5e35b1")
        ax.axvline(3, color="red", ls="--", lw=1)
        contese = 100 * (marg < 3).mean()
        senza = 100 * (stats["margine_min_sigma"] == np.inf).mean()
        ax.set(xlabel="margine minimo sulla seconda scelta (σ della previsione)",
               ylabel="n. tracce",
               title=f"F — quanto erano contesi i collegamenti\n"
                     f"sotto 3σ: {contese:.1f}% — mai contesi: {senza:.0f}%")
    else:
        ax.set(title="F — nessun collegamento conteso")
    ax.grid(alpha=0.3)

    ax = axes[1, 1]
    turn = stats["median_turn_deg"].dropna()
    ax.hist(turn, bins=36, range=(0, 180), color="#fb8c00")
    ax.axvline(120, color="red", ls="--", lw=1)
    frac = stats["frac_turn_gt_120"].mean()
    ax.set(xlabel="angolo fra passi successivi (°)", ylabel="n. tracce",
           title=f"D — cambi di direzione  (passi oltre 120°: {100 * frac:.1f}%)")
    ax.grid(alpha=0.3)

    fig.tight_layout()
    return fig


# ---------------------------------------------------------------------------
def esegui_su_file(blobs, out_dir=None, max_dist=None, max_speed=250.0,
                   max_gap=LinkParams.max_gap, gap_dist=None, min_len=LinkParams.min_len,
                   t0=None, t1=None, roi_um=None, etichetta="", fmt=None, stampa=print,
                   n_ricampioni=LinkParams.n_ricampioni, min_affidabilita=0.0):
    """Linking a partire da una tabella di blob: ritaglio, linking, salvataggi, figure.

    Usata sia dalla riga di comando sia dalla pipeline, per avere un solo percorso di
    codice. Ritorna il dizionario dei file prodotti.
    """
    blobs = Path(blobs)
    filtri = filtri_ritaglio(t0, t1, roi_um)
    det = read_table(blobs, filtri=filtri)
    if filtri:
        stampa(f"ritaglio: {len(det)} blob selezionati"
               + (f", frame {t0}-{t1}" if t0 is not None or t1 is not None else "")
               + (f", ROI µm z {roi_um[0]:.0f}-{roi_um[1]:.0f} y {roi_um[2]:.0f}-{roi_um[3]:.0f} "
                  f"x {roi_um[4]:.0f}-{roi_um[5]:.0f}" if roi_um else ""))
    if det.empty:
        raise ValueError("nessun blob dentro il ritaglio richiesto")

    suffisso = blobs.suffix.lstrip(".")
    fmt = fmt or (suffisso if suffisso in FORMATS else "parquet")
    dt_s = None
    if "t_s" in det and det["t_s"].notna().any():
        u = np.unique(det["t_s"].dropna())
        dt_s = float(np.median(np.diff(u))) if len(u) > 1 else None
    gate = max_dist if max_dist is not None else (
        gate_from_dt(dt_s, max_speed) if dt_s else LinkParams.max_dist_um)
    p = LinkParams(gate, max_gap, gap_dist if gap_dist is not None else gate * 1.25, min_len,
                   n_ricampioni=n_ricampioni)

    out_dir = Path(out_dir) if out_dir else blobs.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = blobs.stem.replace("_blobs", "") + (f"_{etichetta}" if etichetta else "")

    stampa(f"{len(det)} detection su {det['frame'].nunique()} frame"
           + (f", dt={dt_s:.4f} s" if dt_s else "") + f" — gate {p.max_dist_um:.1f} µm")
    tracks, stats, info = run_link(det, p)
    if min_affidabilita > 0 and "affidabilita_media" in stats:
        tieni = stats.loc[stats["affidabilita_media"].fillna(1.0) >= min_affidabilita, "particle"]
        info["scartate_per_affidabilita"] = int(stats["particle"].nunique() - len(tieni))
        tracks = tracks[tracks["particle"].isin(tieni)]
        stats = stats[stats["particle"].isin(tieni)]
        info["n_tracce_tenute"] = int(tracks["particle"].nunique())
    for k, v in info.items():
        stampa(f"  {k}: {v}")
    if "affidabilita_media" in stats and stats["affidabilita_media"].notna().any():
        a_ = stats["affidabilita_media"]
        m_ = stats["margine_min_sigma"]
        finiti = m_.replace(np.inf, np.nan).dropna()
        stampa(f"  affidabilita': mediana {a_.median():.2f}, "
               f"sotto 0.5 il {100 * (a_ < 0.5).mean():.1f}% delle tracce")
        stampa(f"  collegamenti contesi: {100 * (m_ != np.inf).mean():.1f}% delle tracce ne ha almeno uno"
               + (f", margine mediano {finiti.median():.1f}σ" if len(finiti) else ""))

    from ApKit4D.io_table import write_table
    prodotti = {"tracks": write_table(tracks, table_path(out_dir, stem, "tracks", fmt)),
                "stats": write_table(stats, table_path(out_dir, stem, "track_stats", "csv"))}
    fig = make_diagnostics(tracks, stats, info, p, stem, dt_s)
    diag = out_dir / f"{stem}_tracks_diagnostics.png"
    fig.savefig(diag, dpi=150, bbox_inches="tight")
    plt.close(fig)
    prodotti["diagnostiche"] = diag
    prodotti["parametri"] = out_dir / f"{stem}_tracks_params.json"
    prodotti["parametri"].write_text(
        json.dumps({"blobs": str(blobs), "link": p.to_dict(), **info}, indent=2))
    stampa(f"-> {prodotti['tracks']}")
    return prodotti


def main():
    ap = argparse.ArgumentParser(description="ApKit4D — linking LAP dei blob in traiettorie")
    ap.add_argument("blobs_csv", type=Path, help="tabella dei blob (.parquet o .csv) da ApKit4D.batch")
    ap.add_argument("--max-dist", type=float, default=None,
                    help="raggio di ricerca in µm (default: --max-speed x dt del file)")
    ap.add_argument("--max-speed", type=float, default=250.0,
                    help="velocita' massima attesa (µm/s), usata per dedurre il gate")
    ap.add_argument("--max-gap", type=int, default=LinkParams.max_gap)
    ap.add_argument("--gap-dist", type=float, default=None)
    ap.add_argument("--min-len", type=int, default=LinkParams.min_len)
    ap.add_argument("--ricampioni", type=int, default=LinkParams.n_ricampioni,
                    help="ricampionamenti per l'affidabilita' di ogni collegamento "
                         "(0 = non calcolarla, piu' veloce)")
    ap.add_argument("--min-affidabilita", type=float, default=0.0,
                    help="scarta le tracce con affidabilita' media sotto questo valore")
    ap.add_argument("--out", type=Path, default=None, help="cartella (default: quella dei blob)")
    ap.add_argument("--t0", type=int, default=None, help="primo frame del ritaglio")
    ap.add_argument("--t1", type=int, default=None, help="ultimo frame del ritaglio")
    ap.add_argument("--roi-um", default=None, metavar="z0,z1,y0,y1,x0,x1",
                    help="ritaglio spaziale in µm: solo i blob dentro questo volume")
    ap.add_argument("--etichetta", default="", metavar="NOME",
                    help="suffisso per i file prodotti, per non sovrascrivere un linking "
                         "precedente fatto su un altro ritaglio")
    ap.add_argument("--format", choices=FORMATS, default=None,
                    help="formato di uscita (default: lo stesso del file di ingresso)")
    a = ap.parse_args()
    try:
        esegui_su_file(a.blobs_csv, a.out, a.max_dist, a.max_speed, a.max_gap, a.gap_dist,
                       a.min_len, a.t0, a.t1,
                       [float(v) for v in a.roi_um.split(",")] if a.roi_um else None,
                       a.etichetta, a.format, n_ricampioni=a.ricampioni,
                       min_affidabilita=a.min_affidabilita)
    except ValueError as e:
        sys.exit(str(e))


if __name__ == "__main__":
    main()
