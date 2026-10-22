"""
gui.py
======
App napari: si sceglie un .czi, si regola il preprocessing guardando il volume in 2D/3D,
si tara il blob finder sul frame corrente, poi si lancia il batch.

Livelli:
    raw            (T, Z, Y, X) lazy dal .czi: il cursore T di napari legge un volume alla volta
    preprocessato  volume del frame corrente dopo ROI + preprocessing, in [0, 1]
    blob           centroidi dei blob del frame corrente (in µm)
    segmenti       etichette del watershed (opzionale)
    ROI attiva     riquadro giallo della ROI in uso (lo ridisegna l'app)
    ROI disegno    livello vuoto dove disegni tu: poi "ROI XY dal rettangolo"

Contrasto, colormap e opacita' dei livelli restano ai controlli di napari: l'app non li
riscrive dopo aver creato il livello.

Ogni modifica di parametro o di frame ricalcola in un thread separato (con 300 ms di
debounce), quindi la finestra resta reattiva; un risultato arrivato dopo una modifica
piu' recente viene scartato.
"""

import subprocess
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
from magicgui import widgets as W
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
from matplotlib.figure import Figure
from napari.qt.threading import thread_worker
from qtpy.QtCore import QTimer

from ApKit4D import params as P, pipeline, roi_formati
from ApKit4D.io_table import FORMATS, find_table, read_table
from ApKit4D.blobfinder import BlobParams, find_blobs
from ApKit4D.io_czi import CziSource, suggest_z_range
from ApKit4D.preprocess import (BG_MODES, PreprocParams, denoise_and_background, roi_offset,
                               roi_slices, suggest_window, window)


# ----------------------------------------------------------------------------
# calcolo (senza Qt: gira nel thread di lavoro)
# ----------------------------------------------------------------------------
def compute_frame(vol, voxel, pp: PreprocParams, bp: BlobParams, do_blobs: bool, want_labels: bool):
    sl = roi_slices(pp, vol.shape)
    off = roi_offset(pp, vol.shape)
    raw_roi = vol[sl]
    au = denoise_and_background(raw_roi, pp, voxel)
    img = window(au, pp, voxel)

    nz = au[au > 0]
    top = max(float(pp.clip_hi) * 1.3, float(np.percentile(nz, 99.99)) if nz.size else 1.0)
    h_in = np.histogram(nz, bins=256, range=(0, top)) if nz.size else None
    h_out = np.histogram(img[img > 0], bins=128, range=(0, 1))

    # `au` (il volume in AU dopo denoise e fondo) NON viene restituito: sono altri 100 MB
    # tenuti in vita per tutta la sessione solo per il pulsante dei percentili, che se lo
    # ricalcola in una frazione di secondo.
    res = {"img": img, "off": off, "h_in": h_in, "h_out": h_out,
           "frac_sat": float((au >= pp.clip_hi).mean()), "blobs": None}
    if do_blobs:
        df, labels, seed_resp = find_blobs(img, bp, voxel, intensity=raw_roi,
                                           offset=off, return_labels=want_labels)
        res.update(blobs=df, labels=labels, seed_resp=seed_resp)
    return res


# ----------------------------------------------------------------------------
class HistPanel:
    """Tre istogrammi: intensita' prima della finestra (con lo/hi), uscita [0, 1],
    risposta LoG dei candidati (con la soglia).

    Le tre linee verticali si trascinano col mouse. Il ricalcolo parte al rilascio,
    non durante il trascinamento: ogni valore intermedio costerebbe un preprocessing
    (e un blob finder) dell'intero volume.
    """

    def __init__(self, on_window, on_threshold):
        self.on_window = on_window          # (lo, hi) -> None
        self.on_threshold = on_threshold    # thr -> None
        self.fig = Figure(figsize=(3.2, 6), layout="constrained")
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setMinimumSize(320, 540)
        self.ax_in, self.ax_out, self.ax_seed = self.fig.subplots(3, 1)
        self._lines = {}                    # 'lo' | 'hi' | 'thr' -> Line2D
        self._drag = None
        for ev, cb in (("button_press_event", self._press),
                       ("motion_notify_event", self._motion),
                       ("button_release_event", self._release)):
            self.canvas.mpl_connect(ev, cb)

    # ------------------------------------------------------------ trascinamento
    def _press(self, ev):
        if ev.xdata is None:
            return
        if ev.inaxes is self.ax_in:
            candidates = {k: self._lines[k] for k in ("lo", "hi") if k in self._lines}
        elif ev.inaxes is self.ax_seed and "thr" in self._lines:
            candidates = {"thr": self._lines["thr"]}
        else:
            return
        # la piu' vicina al click, purche' entro il 10% della larghezza dell'asse
        x0, x1 = ev.inaxes.get_xlim()
        tol = 0.1 * abs(x1 - x0)
        key, dist = min(((k, abs(ln.get_xdata()[0] - ev.xdata)) for k, ln in candidates.items()),
                        key=lambda kv: kv[1])
        if dist <= tol:
            self._drag = key

    def _motion(self, ev):
        if self._drag is None or ev.xdata is None:
            return
        ln = self._lines[self._drag]
        ln.set_xdata([ev.xdata, ev.xdata])
        self.canvas.draw_idle()

    def _release(self, ev):
        key, self._drag = self._drag, None
        if key is None:
            return
        x = float(self._lines[key].get_xdata()[0])
        if key == "thr":
            self.on_threshold(max(0.0, x))
        else:
            lo = float(self._lines["lo"].get_xdata()[0])
            hi = float(self._lines["hi"].get_xdata()[0])
            self.on_window(max(0.0, min(lo, hi)), max(lo, hi))

    # ------------------------------------------------------------ disegno
    def draw(self, res, pp: PreprocParams, bp: BlobParams):
        a = self.ax_in
        a.clear()
        if res["h_in"] is not None:
            c, e = res["h_in"]
            a.stairs(c, e, fill=True, color="#607d8b")
            a.set_yscale("log")
        self._lines["lo"] = a.axvline(pp.clip_lo, color="#1e88e5", lw=1.6)
        self._lines["hi"] = a.axvline(pp.clip_hi, color="#e53935", lw=1.6)
        a.set_title(f"ingresso (AU, >0) — trascina lo/hi — sopra hi: {100 * res['frac_sat']:.3f}%",
                    fontsize=8)
        a.tick_params(labelsize=7)

        a = self.ax_out
        a.clear()
        c, e = res["h_out"]
        a.stairs(c, e, fill=True, color="#8e24aa")
        a.set_yscale("log")
        a.set_title("uscita preprocessing [0, 1]", fontsize=8)
        a.tick_params(labelsize=7)

        a = self.ax_seed
        a.clear()
        sr = res.get("seed_resp")
        if sr is not None and len(sr):
            a.hist(sr, bins=60, color="#fb8c00")
            n_ok = 0 if res["blobs"] is None else len(res["blobs"])
            a.set_title(f"risposta LoG dei semi — trascina la soglia — {n_ok} blob", fontsize=8)
        else:
            a.set_title("risposta LoG dei semi (premi 'Trova blob')", fontsize=8)
        self._lines["thr"] = a.axvline(bp.threshold, color="#e53935", lw=1.6)
        a.tick_params(labelsize=7)
        self.canvas.draw_idle()


# ----------------------------------------------------------------------------
class LightfieldApp:
    def __init__(self, viewer, czi_path=None):
        self.viewer = viewer
        self.src = None
        self.stem = None
        self.pp = PreprocParams()
        self.bp = BlobParams()
        self._vol_cache = (None, None)      # (t, volume)
        self._last = None                   # ultimo risultato
        self._gen = 0
        self._busy = False
        self._pending = False
        self._force_blobs = False
        self._syncing = False

        self._timer = QTimer()
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._refresh)

        self._jobs = []
        self._job_timer = QTimer()
        self._job_timer.setInterval(2000)
        self._job_timer.timeout.connect(self._poll_jobs)

        self._build()
        viewer.dims.events.current_step.connect(self._on_step)

        czis = P.list_czis()
        if czi_path is not None:
            self.open(Path(czi_path))
        elif czis:
            self.w_file.value = czis[0].name

    # ------------------------------------------------------------------ widget
    def _build(self):
        czis = [p.name for p in P.list_czis()]
        self.w_file = W.ComboBox(label="file (data/raw)", choices=czis or [""])
        self.w_channel = W.SpinBox(label="canale", value=0, min=0, max=16)
        self.w_open = W.PushButton(text="Apri")
        self.w_browse = W.FileEdit(label="oppure sfoglia", mode="r", filter="*.czi",
                                   value=str(P.DATA_RAW))
        self.w_info = W.Label(value="nessun file aperto")
        self.w_open.changed.connect(lambda: self.open(P.DATA_RAW / self.w_file.value))
        self.w_browse.changed.connect(
            lambda: self.open(Path(str(self.w_browse.value)))
            if str(self.w_browse.value).endswith(".czi") else None)
        file_box = W.Container(widgets=[self.w_file, self.w_channel, self.w_open, self.w_browse,
                                        self.w_info])

        # ROI
        self.w_z0 = W.SpinBox(label="z0", min=0, max=10000)
        self.w_z1 = W.SpinBox(label="z1", min=0, max=10000)
        self.w_zauto = W.PushButton(text="Z automatico (frame corrente)")
        self.w_y0 = W.SpinBox(label="y0", min=0, max=100000)
        self.w_y1 = W.SpinBox(label="y1", min=0, max=100000)
        self.w_x0 = W.SpinBox(label="x0", min=0, max=100000)
        self.w_x1 = W.SpinBox(label="x1", min=0, max=100000)
        self.w_roi_rect = W.PushButton(text="ROI XY dal rettangolo")
        self.w_roi_full = W.PushButton(text="ROI intera")
        self.w_t0 = W.SpinBox(label="t0 (batch)", min=0, max=10 ** 6)
        self.w_t1 = W.SpinBox(label="t1 (batch)", min=0, max=10 ** 6)
        # la stessa ROI scritta come riquadro + intervalli numerati da 1: e' la notazione
        # di altri programmi di analisi, si incolla di la' o di qua senza conti a mano
        self.w_av_bounds = W.LineEdit(
            label="riquadro x,y,largh,alt",
            tooltip="Angolo in alto a sinistra piu' larghezza e altezza, in pixel contati "
                    "da 0. Esempio: 106, 106, 300, 300")
        self.w_av_planes = W.LineEdit(
            label="piani (da 1)", tooltip="Intervallo di slice Z numerate da 1, es. 20-60")
        self.w_av_times = W.LineEdit(
            label="frame (da 1)", tooltip="Intervallo di volumi numerati da 1, es. 1-600")
        self.w_av_apply = W.PushButton(
            text="Applica questi valori",
            tooltip="Converte riquadro, piani e frame nella ROI dei campi qui sopra.")
        self.w_av_apply.changed.connect(self._roi_da_testo)
        self.w_zauto.changed.connect(self._zauto)
        self.w_roi_rect.changed.connect(self._roi_from_rect)
        self.w_roi_full.changed.connect(self._roi_full)
        roi_box = W.Container(widgets=[self.w_z0, self.w_z1, self.w_zauto, self.w_y0, self.w_y1,
                                       self.w_x0, self.w_x1, self.w_roi_rect, self.w_roi_full,
                                       self.w_t0, self.w_t1,
                                       W.Label(value="— stessa ROI, altra notazione —"),
                                       self.w_av_bounds, self.w_av_planes, self.w_av_times,
                                       self.w_av_apply])

        # preprocessing
        F = W.FloatSpinBox
        self.pp_widgets = {
            "denoise_xy_um": F(label="denoise σ XY (µm)", min=0, max=50, step=0.5),
            "denoise_z_um": F(label="denoise σ Z (µm)", min=0, max=200, step=5),
            "bg_mode": W.ComboBox(label="fondo", choices=list(BG_MODES)),
            "bg_percentile": F(label="percentile fondo", min=0, max=100, step=1),
            "bg_sigma_xy_um": F(label="σ fondo XY (µm)", min=5, max=1000, step=5),
            "clip_lo": F(label="finestra lo (AU)", min=0, max=65535, step=1),
            "clip_hi": F(label="finestra hi (AU)", min=1, max=65535, step=1),
            "log": W.CheckBox(label="log"),
            "gamma": W.FloatSlider(label="gamma", min=0.2, max=3.0, step=0.05),
            "clahe": W.CheckBox(label="CLAHE 3D (lento)"),
            "clahe_clip": F(label="CLAHE clip", min=0.001, max=0.2, step=0.005),
            "clahe_kernel_xy_um": F(label="CLAHE kernel XY (µm)", min=20, max=1000, step=10),
        }
        self.w_lo_pct = F(label="percentile lo", value=1.0, min=0, max=50, step=0.5)
        self.w_hi_pct = F(label="percentile hi", value=99.9, min=50, max=100, step=0.05)
        self.w_suggest = W.PushButton(text="Finestra dai percentili (frame corrente)")
        self.w_suggest.changed.connect(self._suggest_window)
        pre_box = W.Container(widgets=[*self.pp_widgets.values(), self.w_lo_pct, self.w_hi_pct,
                                       self.w_suggest])

        # blob finder
        self.bp_widgets = {
            "diameter_xy_um": F(label="diametro XY (µm)", min=2, max=200, step=1),
            "diameter_z_um": F(label="diametro Z (µm)", min=5, max=500, step=5),
            "threshold": F(label="soglia risposta LoG", min=0, max=5, step=0.01),
            "split": F(label="separazione (x diametro)", min=0.1, max=3, step=0.05),
            "grow_frac": F(label="confine (x picco)", min=0.01, max=0.99, step=0.05),
            "min_volume_um3": F(label="volume min (µm³)", min=0, max=1e7, step=100),
            "max_volume_um3": F(label="volume max (µm³)", min=0, max=1e9, step=1000),
        }
        self.w_same_d = W.CheckBox(
            label="diametro Z = diametro XY", value=False,
            tooltip="Un solo diametro per tutti gli assi. Utile per riprodurre analisi fatte "
                    "con programmi che non separano XY e Z; qui conviene tenerli distinti, "
                    "perche' la PSF allunga la cellula lungo Z molto piu' del suo diametro.")
        self.w_same_d.changed.connect(self._on_same_diameter)
        self.w_auto = W.CheckBox(label="aggiorna blob a ogni modifica", value=False)
        self.w_labels = W.CheckBox(label="mostra segmenti", value=False)
        self.w_find = W.PushButton(text="Trova blob (frame corrente)")
        self.w_bres = W.Label(value="")
        self.w_find.changed.connect(self._find_now)
        self.w_auto.changed.connect(lambda: self._schedule())
        self.w_labels.changed.connect(lambda: self._schedule(force_blobs=True))
        blob_box = W.Container(widgets=[*self.bp_widgets.values(), self.w_same_d, self.w_auto,
                                        self.w_labels,
                                        self.w_find, self.w_bres])

        # batch
        self.w_out = W.FileEdit(
            label="output", mode="d", value=str(P.DATA_OUT),
            tooltip="Dove finiscono la tabella dei blob, i parametri usati e il log.")
        self.w_workers = W.SpinBox(
            label="processi", value=16, min=1, max=64,
            tooltip="Quanti processi lavorano in parallelo sulla detection: i frame vengono "
                    "divisi fra loro. Ogni processo usa ~1.1 GB di RAM al picco, quindi il "
                    "batch riduce da solo il numero se la memoria libera non basta.\n"
                    "Questa macchina ha 64 core: 16-32 e' un buon intervallo.")
        self.w_format = W.ComboBox(
            label="formato", choices=list(FORMATS),
            tooltip="parquet: ~5 volte piu' piccolo e molto piu' rapido da rileggere, "
                    "perche' carica solo le colonne (e le righe) che servono.\n"
                    "csv: piu' voluminoso, ma apribile con qualunque programma.")
        self.w_tracks_file = W.FileEdit(label="file tracce", mode="r",
                                        filter="*.parquet *.csv")
        self.w_tr_min_len = W.SpinBox(label="lunghezza minima", value=10, min=2, max=10000)
        self.w_tr_max = W.SpinBox(label="max traiettorie", value=500, min=1, max=100000)
        self.w_tr_tail = W.SpinBox(label="coda (frame)", value=20, min=0, max=1000)
        self.w_tr_color = W.ComboBox(label="colore per",
                                     choices=["velocita'", "lunghezza", "traccia"])
        self.w_tr_load = W.PushButton(text="Carica traiettorie sul volume")
        self.w_tr_info = W.Label(value="")
        self.w_tr_load.changed.connect(self._load_tracks)
        for w in (self.w_tr_tail, self.w_tr_color):
            w.changed.connect(self._restyle_tracks)
        # --- ispezione dei collegamenti contesi ---
        self.w_inc_carica = W.PushButton(
            text="Trova gli incroci contesi",
            tooltip="Elenca i punti in cui il tracker aveva piu' di un candidato, ordinati "
                    "dal piu' ambiguo. Sono i punti in cui la traiettoria potrebbe aver "
                    "scambiato una cellula con un'altra.")
        self.w_inc_n = W.SpinBox(label="incrocio n.", value=0, min=0, max=0,
                                 tooltip="0 = il piu' ambiguo di tutti.")
        self.w_inc_zoom = W.FloatSlider(label="zoom", value=2.5, min=0.5, max=10, step=0.5,
                                        tooltip="Quanto avvicinare la vista sull'incrocio.")
        self.w_inc_vai = W.PushButton(
            text="Vai all'incrocio",
            tooltip="Porta il cursore al fotogramma giusto, centra la vista sul punto e "
                    "mostra solo le traiettorie che si incrociano li'.")
        self.w_inc_info = W.Label(value="")
        self.w_inc_carica.changed.connect(self._carica_incroci)
        self.w_inc_vai.changed.connect(self._vai_incrocio)
        tracks_box = W.Container(widgets=[self.w_tracks_file, self.w_tr_min_len, self.w_tr_max,
                                          self.w_tr_tail, self.w_tr_color, self.w_tr_load,
                                          self.w_tr_info,
                                          W.Label(value="— collegamenti contesi —"),
                                          self.w_inc_carica, self.w_inc_n, self.w_inc_zoom,
                                          self.w_inc_vai,
                                          self.w_inc_info])

        self.w_batch_info = W.Label(value="")
        self.w_run = W.PushButton(
            text="Esegui batch t0..t1",
            tooltip="Avvia la detection su tutti i frame dell'intervallo, con la ROI e i "
                    "parametri del riepilogo qui sopra. Gira in un processo separato: "
                    "continua anche chiudendo l'app.")
        self.w_run_info = W.Label(value="")
        self.w_run.changed.connect(self._run_batch)
        self.w_blobs_file = W.FileEdit(
            label="blob da collegare", mode="r", filter="*.parquet *.csv",
            tooltip="La tabella prodotta dal batch. Il linking parte da qui: non serve "
                    "rifare la detection per provare un ritaglio diverso.")
        self.w_link_minlen = W.SpinBox(
            label="punti minimi", value=5, min=2, max=1000,
            tooltip="Traiettorie piu' corte di cosi' vengono scartate: sotto i 5 punti le "
                    "statistiche sono dominate dal rumore.")
        self.w_link_maxspeed = W.FloatSpinBox(
            label="velocita' max (µm/s)", value=250, min=10, max=5000, step=10,
            tooltip="Da qui si ricava il raggio di ricerca: velocita' x dt. Con dt=0.0505 s "
                    "250 µm/s danno 12.6 µm.\nChlamydomonas nuota a 100-200 µm/s: alzarlo "
                    "troppo moltiplica i candidati e porta a scambi fra cellule.")
        self.w_link_gap = W.SpinBox(
            label="buchi colmabili", value=3, min=0, max=20,
            tooltip="Quanti frame consecutivi senza detection puo' saltare una traccia prima "
                    "di spezzarsi. A 0 ogni detection mancata interrompe la traiettoria.")
        self.w_link_ritaglio = W.CheckBox(
            label="solo la ROI e i frame qui sopra", value=True,
            tooltip="Collega solo i blob dentro la ROI e l'intervallo del pannello 2. Il "
                    "filtro viene applicato durante la lettura del file, quindi il resto "
                    "non viene nemmeno caricato in memoria.")
        self.w_link_etichetta = W.LineEdit(
            label="etichetta",
            tooltip="Nome del ritaglio: scrivendo 'centro' i risultati finiscono in "
                    "<esperimento>_centro_tracks.parquet, senza sovrascrivere gli altri.")
        self.w_link_run = W.PushButton(text="Esegui linking")
        self.w_link_info = W.Label(value="")
        self.w_link_run.changed.connect(self._run_link)
        batch_box = W.Container(widgets=[
            self.w_batch_info, self.w_out, self.w_workers, self.w_format, self.w_run,
            self.w_run_info,
            W.Label(value="— linking sui blob gia' calcolati —"),
            self.w_blobs_file, self.w_link_minlen, self.w_link_maxspeed, self.w_link_gap,
            self.w_link_ritaglio, self.w_link_etichetta, self.w_link_run, self.w_link_info])

        for w in list(self.pp_widgets.values()) + list(self.bp_widgets.values()) + \
                [self.w_z0, self.w_z1, self.w_y0, self.w_y1, self.w_x0, self.w_x1,
                 self.w_t0, self.w_t1]:
            w.changed.connect(self._on_param)

        # --- 7 · Pipeline ---
        self.w_pl_nome = W.LineEdit(label="nome",
                                    tooltip="Con che nome salvare la configurazione corrente.")
        self.w_pl_note = W.LineEdit(label="note",
                                    tooltip="Una riga per ricordarsi a cosa serve questa pipeline.")
        self.w_pl_salva = W.PushButton(
            text="Salva pipeline (stato attuale)",
            tooltip="Scrive in pipelines/<nome>.json file, ROI, frame, preprocessing, blob "
                    "finder e linking cosi' come sono adesso.")
        self.w_pl_elenco = W.ComboBox(label="pipeline salvate", choices=[])
        self.w_pl_carica = W.PushButton(
            text="Carica nei pannelli",
            tooltip="Rimette nei pannelli 2-5 i parametri della pipeline scelta, senza eseguirla.")
        self.w_pl_solo = W.ComboBox(label="esegui", choices=["tutto", "detection", "linking"])
        self.w_pl_esegui = W.PushButton(
            text="Esegui pipeline",
            tooltip="Lancia detection e linking in sequenza, in un processo separato.")
        self.w_pl_info = W.Label(value="")
        self.w_pl_salva.changed.connect(self._salva_pipeline)
        self.w_pl_carica.changed.connect(self._carica_pipeline)
        self.w_pl_esegui.changed.connect(self._esegui_pipeline)
        pipeline_box = W.Container(widgets=[
            self.w_pl_nome, self.w_pl_note, self.w_pl_salva,
            W.Label(value="— pipeline gia' salvate —"),
            self.w_pl_elenco, self.w_pl_carica, self.w_pl_solo, self.w_pl_esegui,
            self.w_pl_info])

        self.hist = HistPanel(self._hist_window, self._hist_threshold)
        v = self.viewer.window
        dock_file = v.add_dock_widget(file_box, area="right", name="1 · File")
        v.add_dock_widget(roi_box, area="right", name="2 · ROI", tabify=True)
        v.add_dock_widget(pre_box, area="right", name="3 · Preprocessing", tabify=True)
        v.add_dock_widget(blob_box, area="right", name="4 · Blob finder", tabify=True)
        v.add_dock_widget(batch_box, area="right", name="5 · Batch", tabify=True)
        v.add_dock_widget(tracks_box, area="right", name="6 · Traiettorie", tabify=True)
        v.add_dock_widget(pipeline_box, area="right", name="7 · Pipeline", tabify=True)
        v.add_dock_widget(self.hist.canvas, area="left", name="Istogrammi")
        self._dock_file = dock_file
        self._nomi_passi = ["1 · File", "2 · ROI", "3 · Preprocessing", "4 · Blob finder",
                            "5 · Batch", "6 · Traiettorie", "7 · Pipeline"]
        self._aggiorna_elenco_pipeline()
        self.raise_file_panel()
        # le linguette esistono solo dopo che Qt ha impaginato i dock: si stilano dopo
        QTimer.singleShot(0, self.stile_linguette)
        QTimer.singleShot(400, self.stile_linguette)

    # un colore per passo: le linguette fanno da indice, come i segnalibri di un quaderno
    COLORI_PASSI = ["#1e88e5", "#f9a825", "#8e24aa", "#00897b", "#ef6c00", "#2e7d32",
                    "#c62828"]

    def stile_linguette(self):
        """Linguette verticali e colorate sul bordo destro, una per passo.

        I dock affiancati in Qt finiscono in un QTabBar con etichette minuscole in basso.
        Qui la barra viene girata sul lato (testo verticale), ingrandita, e a ogni linguetta
        viene dato il colore del suo passo piu' un quadratino dello stesso colore.
        """
        from qtpy.QtCore import Qt
        from qtpy.QtGui import QColor, QIcon, QPixmap
        from qtpy.QtWidgets import QTabBar, QTabWidget

        w = self.viewer.window._qt_window
        w.setTabPosition(Qt.RightDockWidgetArea, QTabWidget.East)
        for barra in w.findChildren(QTabBar):
            etichette = [barra.tabText(i) for i in range(barra.count())]
            if not any(e in self._nomi_passi for e in etichette):
                continue
            barra.setStyleSheet(
                "QTabBar::tab { min-height: 120px; padding: 10px 8px; margin: 2px 0; "
                "font-size: 13px; font-weight: 600; border-top-left-radius: 6px; "
                "border-bottom-left-radius: 6px; }"
                "QTabBar::tab:selected { background: #3c4350; }")
            for i, testo in enumerate(etichette):
                if testo not in self._nomi_passi:
                    continue
                colore = QColor(self.COLORI_PASSI[self._nomi_passi.index(testo)])
                barra.setTabTextColor(i, colore)
                quad = QPixmap(14, 14)
                quad.fill(colore)
                barra.setTabIcon(i, QIcon(quad))

    def raise_file_panel(self):
        """Porta in primo piano il pannello 1 · File: senza questo resta selezionato l'ultimo
        dock aggiunto (Batch). Va ripetuto dopo che la finestra e' stata mostrata, altrimenti
        Qt ricalcola le tab e la selezione torna indietro."""
        self._dock_file.raise_()
        QTimer.singleShot(200, self._dock_file.raise_)

    # ------------------------------------------------------------------ file
    def open(self, path: Path):
        """Apre un .czi. Va usato questo pannello, non File > Open di napari: napari cerca un
        plugin lettore e i .czi non ne hanno ('No plugin found capable of reading ...')."""
        try:
            src = CziSource(path, self.w_channel.value)
        except Exception as e:
            self.w_info.value = f"{path.name}\n\nNON APRIBILE — {e}"
            return
        self.src, self.stem = src, P.stem_of(path)
        i = src.info
        dt = f"{i.dt_s:.4f} s ({i.dt_source})" if i.dt_s else f"n.d. ({i.dt_source})"
        self.w_info.value = (f"T={i.n_t}  Z={i.n_z}  Y={i.n_y}  X={i.n_x}\n"
                             f"voxel {i.px_z:.2f} × {i.px_y:.3f} × {i.px_x:.3f} µm\ndt = {dt}")

        saved = P.load(self.stem)
        self.pp = PreprocParams.from_dict(saved.get("preproc"))
        self.bp = BlobParams.from_dict(saved.get("blob"))
        if not saved:  # prima apertura: finestra proposta dal frame 0
            self.pp.clip_lo, self.pp.clip_hi = suggest_window(src.read(0), 1.0, 99.9)
        self._set_ranges()
        self._push_to_widgets(saved)

        for name in ("raw", "preprocessato", "blob", "segmenti", "ROI attiva", "ROI disegno"):
            if name in self.viewer.layers:
                self.viewer.layers.remove(name)
        vox = i.voxel
        raw = self.viewer.add_image(src.as_dask(), name="raw", scale=(1, *vox),
                                    colormap="gray", blending="additive",
                                    contrast_limits=(self.pp.clip_lo, self.pp.clip_hi))
        raw.visible = False
        self.viewer.add_image(np.zeros((1, 1, 1), np.float32), name="preprocessato",
                              scale=vox, colormap="magma", contrast_limits=(0, 1),
                              blending="additive")
        # due livelli distinti: "ROI attiva" e' il riquadro che disegna l'app e che verrebbe
        # sovrascritto a ogni modifica; "ROI disegno" resta tuo, non lo tocca nessuno.
        roi_shown = self.viewer.add_shapes(name="ROI attiva", ndim=2, scale=vox[1:],
                                           edge_color="yellow", face_color="transparent",
                                           edge_width=2)
        # non modificabile: disegnandoci dentro in vista 3D ci finiscono forme con tre
        # coordinate invece di due, e da quel momento napari va in errore a ogni ridisegno
        roi_shown.editable = False
        draw = self.viewer.add_shapes(name="ROI disegno", ndim=2, scale=vox[1:],
                                      edge_color="cyan", face_color="transparent", edge_width=2)
        self.viewer.layers.selection = {draw}
        self.viewer.dims.axis_labels = ("t", "z", "y", "x")
        self.viewer.dims.set_point(0, 0)
        self._show_roi_rect()
        self._mostra_roi_testo()
        self._show_batch_summary()
        for suffisso, widget in (("tracks", self.w_tracks_file), ("blobs", self.w_blobs_file)):
            trovato = find_table(str(self.w_out.value), self.stem, suffisso)
            if trovato is not None:
                widget.value = str(trovato)
        self.viewer.reset_view()
        self._schedule()

    def _set_ranges(self):
        i = self.src.info
        for w, n in ((self.w_z0, i.n_z), (self.w_z1, i.n_z), (self.w_y0, i.n_y),
                     (self.w_y1, i.n_y), (self.w_x0, i.n_x), (self.w_x1, i.n_x),
                     (self.w_t0, i.n_t), (self.w_t1, i.n_t)):
            w.max = n - 1

    def _push_to_widgets(self, saved):
        """Parametri -> widget, senza far partire un ricalcolo per ogni campo."""
        self._syncing = True
        try:
            sh = (self.src.info.n_z, self.src.info.n_y, self.src.info.n_x)
            sl = roi_slices(self.pp, sh)
            for (w0, w1), s in zip(((self.w_z0, self.w_z1), (self.w_y0, self.w_y1),
                                    (self.w_x0, self.w_x1)), sl):
                w0.value, w1.value = s.start, s.stop - 1
            self.w_t0.value = saved.get("t0", 0)
            self.w_t1.value = min(saved.get("t1", self.src.info.n_t - 1), self.src.info.n_t - 1)
            for k, w in self.pp_widgets.items():
                w.value = getattr(self.pp, k)
            for k, w in self.bp_widgets.items():
                w.value = getattr(self.bp, k)
        finally:
            self._syncing = False

    def _pull_from_widgets(self):
        roi = dict(z0=self.w_z0.value, z1=self.w_z1.value, y0=self.w_y0.value,
                   y1=self.w_y1.value, x0=self.w_x0.value, x1=self.w_x1.value)
        self.pp = replace(self.pp, **roi, **{k: w.value for k, w in self.pp_widgets.items()})
        self.bp = replace(self.bp, **{k: w.value for k, w in self.bp_widgets.items()})

    def _save(self):
        if self.stem:
            P.save(self.stem, {"czi": str(self.src.path), "channel": self.src.channel,
                               "t0": self.w_t0.value, "t1": self.w_t1.value,
                               "preproc": self.pp.to_dict(), "blob": self.bp.to_dict()})

    # ------------------------------------------------------------------ eventi
    def _on_param(self, *_):
        if self._syncing or self.src is None:
            return
        self._pull_from_widgets()
        if self.w_same_d.value:
            self._apply_same_diameter()
        self._save()
        self._show_roi_rect()
        self._mostra_roi_testo()
        self._show_batch_summary()
        self._schedule()

    def _on_step(self, *_):
        if self.src is not None and self._current_t() != getattr(self, "_shown_t", None):
            self._schedule()

    def _current_t(self):
        if self.src is None or self.viewer.dims.ndim < 4:
            return 0
        return int(np.clip(round(self.viewer.dims.point[0]), 0, self.src.info.n_t - 1))

    def _schedule(self, force_blobs=False):
        self._force_blobs = self._force_blobs or force_blobs
        self._timer.start()

    def _find_now(self):
        self._force_blobs = True
        self._refresh()

    # ------------------------------------------------------------------ calcolo
    def _volume(self, t):
        if self._vol_cache[0] != t:
            self._vol_cache = (t, self.src.read(t))
        return self._vol_cache[1]

    def _refresh(self):
        if self.src is None:
            return
        if self._busy:
            self._pending = True
            return
        self._busy = True
        self._gen += 1
        gen, t = self._gen, self._current_t()
        do_blobs = self.w_auto.value or self._force_blobs or \
            (self._last is not None and self._last.get("blobs") is not None)
        self._force_blobs = False
        pp, bp, vox, want_lab = self.pp, self.bp, self.src.info.voxel, self.w_labels.value

        @thread_worker
        def work():
            return compute_frame(self._volume(t), vox, pp, bp, do_blobs, want_lab)

        w = work()
        w.returned.connect(lambda res: self._on_result(res, gen, t, pp, bp))
        w.errored.connect(self._on_error)
        w.finished.connect(self._on_finished)
        w.start()

    def _on_finished(self):
        self._busy = False
        if self._pending:
            self._pending = False
            self._refresh()

    def _on_error(self, e):
        self.w_bres.value = f"errore: {e}"

    def _on_result(self, res, gen, t, pp, bp):
        if gen != self._gen:
            return
        self._last, self._shown_t = res, t
        vox = self.src.info.voxel
        lay = self.viewer.layers["preprocessato"]
        lay.data = res["img"]
        lay.translate = tuple(o * v for o, v in zip(res["off"], vox))
        # contrasto e colormap NON si toccano qui: sono i controlli di napari, e riscriverli
        # a ogni ricalcolo annullava ogni regolazione fatta a mano.

        df = res["blobs"]
        for name in ("blob", "segmenti"):
            if name in self.viewer.layers and (df is None or name == "segmenti"):
                self.viewer.layers.remove(name)
        if df is not None:
            pts = df[["z_um", "y_um", "x_um"]].to_numpy()
            feats = df[["response", "volume_um3", "z_extent", "max_intensity"]]
            if "blob" in self.viewer.layers:
                L = self.viewer.layers["blob"]
                L.data, L.features, L.size = pts, feats, bp.diameter_xy_um
            else:
                self.viewer.add_points(pts, name="blob", features=feats, size=bp.diameter_xy_um,
                                       face_color="#00e676", opacity=0.7,
                                       out_of_slice_display=True)
            if res.get("labels") is not None:
                self.viewer.add_labels(res["labels"], name="segmenti", scale=vox,
                                       translate=lay.translate, opacity=0.4)
            self.w_bres.value = (f"frame {t}: {len(df)} blob  "
                                 f"(volume mediano {df['volume_um3'].median():.0f} µm³, "
                                 f"estensione Z mediana {df['z_extent'].median():.0f} slice)"
                                 if len(df) else f"frame {t}: nessun blob")
        self.hist.draw(res, pp, bp)

    # ------------------------------------------------------------------ azioni
    # ------------------------------------------------------------------ traiettorie
    def _load_tracks(self):
        """Carica <stem>_tracks.csv in un livello Tracks di napari, sopra il volume.

        I CSV interi sono grossi (mezzo GB per Exp-571, 2.5 milioni di punti) e napari non
        regge tutte le tracce insieme: si tengono le piu' lunghe, fino a `max traiettorie`.
        Le colonne z/y/x sono gia' in µm e il tempo e' in frame, quindi il livello va in
        coordinate del mondo (scale 1) e si sovrappone al volume, che ha scale = voxel.
        """
        path = Path(str(self.w_tracks_file.value))
        if not path.is_file():
            self.w_tr_info.value = "scegli un file <stem>_tracks.parquet (o .csv)"
            return
        self.w_tr_info.value = f"lettura di {path.name}..."
        try:
            # solo le colonne che servono: su Exp-571 sono 50 MB invece di 330
            df = read_table(path, columns=["particle", "frame", "z_um", "y_um", "x_um"])
        except (ValueError, KeyError) as e:
            self.w_tr_info.value = f"colonne mancanti nel file: {e}"
            return

        n_tot = df["particle"].nunique()
        size = df.groupby("particle")["frame"].size()
        keep = size[size >= self.w_tr_min_len.value]
        keep = keep.nlargest(self.w_tr_max.value).index
        df = df[df["particle"].isin(keep)].sort_values(["particle", "frame"])
        if df.empty:
            self.w_tr_info.value = "nessuna traccia supera la lunghezza minima"
            return

        xyz = df[["z_um", "y_um", "x_um"]].to_numpy()
        data = np.column_stack([df["particle"].to_numpy(), df["frame"].to_numpy(), xyz])

        # velocita' per punto (µm/frame), per la colorazione
        dt = self.src.info.dt_s if self.src and self.src.info.dt_s else 1.0
        step = np.linalg.norm(np.diff(xyz, axis=0), axis=1)
        same = df["particle"].to_numpy()[1:] == df["particle"].to_numpy()[:-1]
        speed = np.concatenate([[0.0], np.where(same, step, 0.0)]) / dt
        feats = pd.DataFrame({"velocita'": speed,
                              "lunghezza": df["particle"].map(size).to_numpy(),
                              "traccia": df["particle"].to_numpy()})

        if "traiettorie" in self.viewer.layers:
            self.viewer.layers.remove("traiettorie")
        self._tracks_layer = self.viewer.add_tracks(
            data, name="traiettorie", features=feats, tail_length=self.w_tr_tail.value,
            tail_width=3, colormap="turbo", blending="translucent")
        self._restyle_tracks()
        self.w_tr_info.value = (f"{len(keep)} traiettorie su {n_tot} ({len(df)} punti)\n"
                                f"cursore T: la coda mostra gli ultimi "
                                f"{self.w_tr_tail.value} frame")

    # ------------------------------------------------------------------ incroci contesi
    RAGGIO_INCROCIO_UM = 40.0        # quanto intorno al punto si considera "coinvolto"

    def _carica_incroci(self):
        """Elenca i punti in cui il tracker ha dovuto scegliere fra piu' candidati."""
        path = Path(str(self.w_tracks_file.value))
        if not path.is_file():
            self.w_inc_info.value = "scegli prima un file di tracce"
            return
        try:
            df = read_table(path, columns=["particle", "frame", "z_um", "y_um", "x_um",
                                           "margine_sigma", "n_candidati"])
        except (ValueError, KeyError):
            self.w_inc_info.value = ("questo file non ha le colonne dell'affidabilita': "
                                     "rifai il linking con questa versione")
            return
        contesi = df[df["n_candidati"] > 1].copy()
        if contesi.empty:
            self.w_inc_info.value = "nessun collegamento conteso in queste tracce"
            return
        # dal piu' ambiguo: margine piccolo = la seconda scelta era quasi altrettanto buona
        self._incroci = contesi.sort_values("margine_sigma").head(200).reset_index(drop=True)
        self._tracce_complete = df
        self.w_inc_n.max = len(self._incroci) - 1
        self.w_inc_n.value = 0
        self.w_inc_info.value = (f"{len(contesi)} collegamenti contesi su {len(df)} "
                                 f"({100 * len(contesi) / len(df):.2f}%)\n"
                                 f"ne tengo i {len(self._incroci)} piu' ambigui")

    def _vai_incrocio(self):
        """Porta la vista sull'incrocio scelto e mostra le traiettorie coinvolte."""
        inc = getattr(self, "_incroci", None)
        if inc is None or inc.empty:
            self.w_inc_info.value = "premi prima 'Trova gli incroci contesi'"
            return
        r = inc.iloc[int(self.w_inc_n.value)]
        centro = np.array([r.z_um, r.y_um, r.x_um])
        frame = int(r.frame)

        df = self._tracce_complete
        qui = df[df.frame == frame]
        vicine = qui[np.linalg.norm(qui[["z_um", "y_um", "x_um"]].to_numpy() - centro,
                                    axis=1) <= self.RAGGIO_INCROCIO_UM]
        coinvolte = vicine.particle.unique()
        tratti = df[df.particle.isin(coinvolte) & (df.frame.between(frame - 40, frame + 40))]
        tratti = tratti.sort_values(["particle", "frame"])

        for nome in ("incrocio", "tracce dell'incrocio"):
            if nome in self.viewer.layers:
                self.viewer.layers.remove(nome)
        dati = np.column_stack([tratti.particle, tratti.frame,
                                tratti[["z_um", "y_um", "x_um"]].to_numpy()])
        self.viewer.add_tracks(dati, name="tracce dell'incrocio", tail_length=40,
                               tail_width=5, colormap="turbo", blending="translucent")
        self.viewer.add_points(centro[None, :], name="incrocio", size=60, face_color="#ffffff00",
                               border_color="red", border_width=0.12, out_of_slice_display=True)

        self.viewer.dims.set_point(0, frame)
        self.viewer.camera.center = tuple(centro)
        self.viewer.camera.zoom = self.w_inc_zoom.value
        self.w_inc_info.value = (
            f"incrocio {int(self.w_inc_n.value)}/{len(inc) - 1}: frame {frame}, "
            f"margine {r.margine_sigma:.1f}σ, {int(r.n_candidati)} candidati\n"
            f"{len(coinvolte)} traiettorie entro {self.RAGGIO_INCROCIO_UM:.0f} µm — "
            f"muovi il cursore T per vedere l'incrocio")

    def _restyle_tracks(self):
        lay = getattr(self, "_tracks_layer", None)
        if lay is None or "traiettorie" not in self.viewer.layers:
            return
        lay.tail_length = self.w_tr_tail.value
        lay.color_by = self.w_tr_color.value

    def _show_batch_summary(self):
        """Riepilogo di cosa elaborera' il batch. Senza, ci si accorge solo dopo (dal json)
        di aver girato sul volume intero credendo di aver ritagliato una ROI."""
        if self.src is None:
            return
        i = self.src.info
        sz, sy, sx = roi_slices(self.pp, (i.n_z, i.n_y, i.n_x))
        n = (sz.stop - sz.start) * (sy.stop - sy.start) * (sx.stop - sx.start)
        frac = 100 * n / (i.n_z * i.n_y * i.n_x)
        self.w_batch_info.value = (
            f"{'VOLUME INTERO' if frac > 99.9 else 'ROI'}: z {sz.start}-{sz.stop - 1}, "
            f"y {sy.start}-{sy.stop - 1}, x {sx.start}-{sx.stop - 1}  ({frac:.0f}% del volume)\n"
            f"frame {self.w_t0.value}-{self.w_t1.value}  —  soglia blob {self.bp.threshold:g}, "
            f"finestra {self.pp.clip_lo:.0f}-{self.pp.clip_hi:.0f} AU")

    def _mostra_roi_testo(self):
        """Riscrive riquadro, piani e frame a partire dalla ROI corrente."""
        if self.src is None:
            return
        sh = (self.src.info.n_z, self.src.info.n_y, self.src.info.n_x)
        sz, sy, sx = roi_slices(self.pp, sh)
        self._syncing = True
        try:
            self.w_av_bounds.value = roi_formati.format_bounds(sx.start, sx.stop - 1,
                                                               sy.start, sy.stop - 1)
            self.w_av_planes.value = roi_formati.format_range_1based(sz.start, sz.stop - 1)
            self.w_av_times.value = roi_formati.format_range_1based(self.w_t0.value,
                                                                    self.w_t1.value)
        finally:
            self._syncing = False

    def _roi_da_testo(self):
        """Applica riquadro, piani e frame scritti nella notazione numerata da 1."""
        if self.src is None:
            return
        i = self.src.info
        try:
            x0, x1, y0, y1 = roi_formati.parse_bounds(self.w_av_bounds.value)
            z0, z1 = roi_formati.parse_range_1based(self.w_av_planes.value)
            t0, t1 = roi_formati.parse_range_1based(self.w_av_times.value)
        except ValueError as e:
            self.w_info.value = f"valori non validi: {e}"
            return
        clip = lambda v, n: int(np.clip(v, 0, n - 1))
        self._syncing = True
        try:
            self.w_x0.value, self.w_x1.value = clip(x0, i.n_x), clip(x1, i.n_x)
            self.w_y0.value, self.w_y1.value = clip(y0, i.n_y), clip(y1, i.n_y)
            self.w_z0.value, self.w_z1.value = clip(z0, i.n_z), clip(z1, i.n_z)
            self.w_t0.value, self.w_t1.value = clip(t0, i.n_t), clip(t1, i.n_t)
        finally:
            self._syncing = False
        self._on_param()

    def _apply_same_diameter(self):
        w = self.bp_widgets["diameter_z_um"]
        if w.value != self.bp_widgets["diameter_xy_um"].value:
            self._syncing = True
            try:
                w.value = self.bp_widgets["diameter_xy_um"].value
            finally:
                self._syncing = False
            self._pull_from_widgets()

    def _on_same_diameter(self):
        """Un solo diametro per tutti gli assi. Sciolto, il diametro Z resta indipendente,
        che qui conviene: la PSF assiale allunga ogni cellula molto piu' del suo diametro."""
        if self.w_same_d.value:
            self._apply_same_diameter()
            self._schedule(force_blobs=True)

    def _hist_window(self, lo, hi):
        """Linee lo/hi trascinate nell'istogramma -> caselle del pannello Preprocessing."""
        self._syncing = True
        try:
            self.pp_widgets["clip_lo"].value = max(0.0, lo)
            self.pp_widgets["clip_hi"].value = max(lo + 1e-3, hi)
        finally:
            self._syncing = False
        self._on_param()

    def _hist_threshold(self, thr):
        w = self.bp_widgets["threshold"]
        self._force_blobs = True
        w.value = min(max(thr, w.min), w.max)

    def _zauto(self):
        if self.src is None:
            return
        z0, z1, _ = suggest_z_range(self._volume(self._current_t()))
        self.w_z0.value, self.w_z1.value = z0, z1

    def _suggest_window(self):
        if self.src is None:
            return
        vol = self._volume(self._current_t())
        au = denoise_and_background(vol[roi_slices(self.pp, vol.shape)], self.pp,
                                    self.src.info.voxel)
        lo, hi = suggest_window(au, self.w_lo_pct.value, self.w_hi_pct.value)
        del au
        self._syncing = True
        try:
            self.pp_widgets["clip_lo"].value = lo
            self.pp_widgets["clip_hi"].value = hi
        finally:
            self._syncing = False
        self._on_param()

    def _roi_from_rect(self):
        lay = self.viewer.layers["ROI disegno"] if "ROI disegno" in self.viewer.layers else None
        if lay is None or len(lay.data) == 0:
            self.w_info.value = ("disegna prima un rettangolo: seleziona il livello 'ROI disegno' "
                                 "nella lista a sinistra, poi lo strumento rettangolo")
            return
        pts = np.asarray(lay.data[-1])[:, -2:]
        i = self.src.info
        y0, x0 = np.floor(pts.min(axis=0)).astype(int)
        y1, x1 = np.ceil(pts.max(axis=0)).astype(int)
        self._syncing = True
        try:
            self.w_y0.value, self.w_y1.value = int(np.clip(y0, 0, i.n_y - 1)), int(np.clip(y1, 0, i.n_y - 1))
            self.w_x0.value, self.w_x1.value = int(np.clip(x0, 0, i.n_x - 1)), int(np.clip(x1, 0, i.n_x - 1))
        finally:
            self._syncing = False
        self._on_param()   # esplicito: prima si applicava solo se cambiava l'ultimo campo

    def _roi_full(self):
        i = self.src.info
        self._syncing = True
        try:
            self.w_z0.value, self.w_z1.value = 0, i.n_z - 1
            self.w_y0.value, self.w_y1.value = 0, i.n_y - 1
            self.w_x0.value, self.w_x1.value = 0, i.n_x - 1
        finally:
            self._syncing = False
        self._on_param()

    def _show_roi_rect(self):
        if "ROI attiva" not in self.viewer.layers or self.src is None:
            return
        p = self.pp
        sh = (self.src.info.n_z, self.src.info.n_y, self.src.info.n_x)
        _, sy, sx = roi_slices(p, sh)
        rect = np.array([[sy.start, sx.start], [sy.start, sx.stop - 1],
                         [sy.stop - 1, sx.stop - 1], [sy.stop - 1, sx.start]], dtype=float)
        lay = self.viewer.layers["ROI attiva"]
        if lay.ndim > 2:   # il livello aspetta anche le dimensioni davanti (es. z)
            rect = np.hstack([np.zeros((4, lay.ndim - 2)), rect])
        try:
            lay.data = [rect]
            lay.shape_type = ["rectangle"]
            # napari rimette editable=True da solo a ogni cambio di dati o di vista:
            # va riaffermato qui, altrimenti si puo' disegnare in questo livello e basta
            # una forma con un numero diverso di coordinate per mandarlo in errore
            lay.editable = False
        except Exception:
            # livello in uno stato incoerente (forme con numeri di coordinate diversi):
            # si ricrea, tanto e' solo un riquadro di riferimento
            vox = self.src.info.voxel
            self.viewer.layers.remove(lay)
            new = self.viewer.add_shapes([rect[:, -2:]], shape_type="rectangle",
                                         name="ROI attiva", ndim=2, scale=vox[1:],
                                         edge_color="yellow", face_color="transparent",
                                         edge_width=2)
            new.editable = False

    # ------------------------------------------------------------------ pipeline
    def _aggiorna_elenco_pipeline(self):
        nomi = [p.stem for p in pipeline.elenco()]
        self.w_pl_elenco.choices = nomi or [""]

    def _salva_pipeline(self):
        if self.src is None:
            self.w_pl_info.value = "apri prima un file"
            return
        nome = str(self.w_pl_nome.value).strip() or f"{self.stem}"
        p = pipeline.salva(
            nome, self.src.path, self.src.channel, self.pp, self.bp,
            self.w_t0.value, self.w_t1.value, str(self.w_out.value),
            formato=self.w_format.value, workers=self.w_workers.value,
            link={"min_len": self.w_link_minlen.value, "max_speed": self.w_link_maxspeed.value,
                  "max_gap": self.w_link_gap.value, "ritaglio": self.w_link_ritaglio.value},
            etichetta=str(self.w_link_etichetta.value).strip(),
            note=str(self.w_pl_note.value).strip())
        self._aggiorna_elenco_pipeline()
        self.w_pl_elenco.value = p.stem
        self.w_pl_info.value = f"salvata: pipelines/{p.name}"

    def _carica_pipeline(self):
        nome = self.w_pl_elenco.value
        if not nome:
            return
        try:
            d = pipeline.carica(nome)
        except (FileNotFoundError, ValueError) as e:
            self.w_pl_info.value = str(e)
            return
        if self.src is None or str(self.src.path) != d["czi"]:
            self.open(Path(d["czi"]))          # la pipeline porta con se' anche il file
        self.pp = PreprocParams.from_dict(d["preproc"])
        self.bp = BlobParams.from_dict(d["blob"])
        self._push_to_widgets({"t0": d["t0"], "t1": d["t1"]})
        L = d.get("link", {})
        self._syncing = True
        try:
            self.w_link_minlen.value = L.get("min_len", 5)
            self.w_link_maxspeed.value = L.get("max_speed", 250.0)
            self.w_link_gap.value = L.get("max_gap", 3)
            self.w_link_ritaglio.value = L.get("ritaglio", True)
            self.w_link_etichetta.value = d.get("etichetta", "")
            self.w_out.value = d.get("out", str(P.DATA_OUT))
            self.w_format.value = d.get("formato", "parquet")
            self.w_workers.value = d.get("workers", 16)
            self.w_pl_note.value = d.get("note", "")
            self.w_pl_nome.value = d.get("nome", nome)
        finally:
            self._syncing = False
        self._on_param()
        self.w_pl_info.value = f"caricata '{nome}' — i pannelli 2-5 sono aggiornati"

    def _esegui_pipeline(self):
        nome = self.w_pl_elenco.value
        if not nome:
            self.w_pl_info.value = "nessuna pipeline selezionata"
            return
        file_pl = pipeline.percorso(nome)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = Path(str(self.w_out.value))
        out.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, "-m", "ApKit4D.pipeline", str(file_pl)]
        if self.w_pl_solo.value != "tutto":
            cmd += ["--solo", self.w_pl_solo.value]
        self._avvia_processo(cmd, out / f"{nome}_pipeline_{stamp}.log", self.w_pl_info,
                             al_termine=self._dopo_pipeline, nota=f"'{nome}' ({self.w_pl_solo.value})")

    def _dopo_pipeline(self):
        # le tracce portano l'etichetta della pipeline nel nome, i blob no
        etichetta = str(self.w_link_etichetta.value).strip()
        stem_tracce = f"{self.stem}_{etichetta}" if etichetta else self.stem
        for suffisso, stem, widget in (("tracks", stem_tracce, self.w_tracks_file),
                                       ("blobs", self.stem, self.w_blobs_file)):
            trovato = find_table(str(self.w_out.value), stem, suffisso)
            if trovato is not None:
                widget.value = str(trovato)
        self.w_pl_info.value += "\n-> risultati pronti nei pannelli 5 e 6"

    # ------------------------------------------------------------------ processi esterni
    def _avvia_processo(self, cmd, log, widget_info, al_termine=None, nota=""):
        """Lancia un comando in un processo separato e ne mostra l'avanzamento.

        Stessa meccanica per batch e linking: il processo scrive su un log, qui si legge
        l'ultima riga ogni due secondi. Il processo sopravvive alla chiusura dell'app.
        """
        fh = open(log, "w")
        proc = subprocess.Popen(cmd, stdout=fh, stderr=subprocess.STDOUT,
                                cwd=str(P.BASE_DIR), start_new_session=True)
        self._jobs.append({"proc": proc, "log": log, "info": widget_info, "cb": al_termine})
        widget_info.value = f"avviato{(' — ' + nota) if nota else ''}\nlog: {log.name}"
        self._job_timer.start()

    def _poll_jobs(self):
        for j in list(self._jobs):
            try:
                righe = [l.strip() for l in j["log"].read_text().splitlines() if l.strip()]
            except OSError:
                righe = []
            ultima = righe[-1] if righe else "avvio..."
            esito = j["proc"].poll()
            if esito is None:
                j["info"].value = f"in corso — {ultima}\nlog: {j['log'].name}"
                continue
            j["info"].value = (f"{'FINITO' if esito == 0 else f'ERRORE (codice {esito})'} — "
                               f"{ultima}\nlog: {j['log'].name}")
            self._jobs.remove(j)
            if j["cb"] and esito == 0:
                j["cb"]()
        if not self._jobs:
            self._job_timer.stop()

    def _run_batch(self):
        if self.src is None:
            return
        out = Path(self.w_out.value)
        out.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pfile = out / f"{self.stem}_params_{stamp}.json"
        import json
        pfile.write_text(json.dumps({"channel": self.src.channel, "t0": self.w_t0.value,
                                     "t1": self.w_t1.value, "preproc": self.pp.to_dict(),
                                     "blob": self.bp.to_dict()}, indent=2))
        cmd = [sys.executable, "-m", "ApKit4D.batch", str(self.src.path), "--params", str(pfile),
               "--out", str(out), "--workers", str(self.w_workers.value),
               "--format", self.w_format.value]
        self._avvia_processo(cmd, out / f"{self.stem}_batch_{stamp}.log", self.w_run_info,
                             al_termine=self._dopo_batch,
                             nota=f"frame {self.w_t0.value}-{self.w_t1.value}")

    def _dopo_batch(self):
        trovato = find_table(str(self.w_out.value), self.stem, "blobs")
        if trovato is not None:
            self.w_blobs_file.value = str(trovato)

    # ------------------------------------------------------------------ linking
    def roi_um(self):
        """ROI corrente in µm (z0, z1, y0, y1, x0, x1), per ritagliare le detection."""
        i = self.src.info
        sz, sy, sx = roi_slices(self.pp, (i.n_z, i.n_y, i.n_x))
        vox = i.voxel
        return [sz.start * vox[0], (sz.stop - 1) * vox[0],
                sy.start * vox[1], (sy.stop - 1) * vox[1],
                sx.start * vox[2], (sx.stop - 1) * vox[2]]

    def _run_link(self):
        """Linking sui blob gia' calcolati, eventualmente solo su un ritaglio.

        Il ritaglio NON richiede di rifare la detection: i filtri vengono spinti dentro la
        lettura del parquet, quindi le righe fuori dal ritaglio non entrano in memoria.
        """
        blobs = Path(str(self.w_blobs_file.value))
        if not blobs.is_file():
            self.w_link_info.value = "scegli prima la tabella dei blob (<stem>_blobs.parquet)"
            return
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = blobs.parent
        cmd = [sys.executable, "-m", "ApKit4D.link", str(blobs), "--out", str(out),
               "--min-len", str(self.w_link_minlen.value),
               "--max-speed", str(self.w_link_maxspeed.value),
               "--max-gap", str(self.w_link_gap.value)]
        nota = "tutti i blob del file"
        if self.w_link_ritaglio.value and self.src is not None:
            cmd += ["--t0", str(self.w_t0.value), "--t1", str(self.w_t1.value),
                    "--roi-um", ",".join(f"{v:.2f}" for v in self.roi_um())]
            nota = f"ritaglio: frame {self.w_t0.value}-{self.w_t1.value} + ROI corrente"
        etichetta = str(self.w_link_etichetta.value).strip()
        if etichetta:
            cmd += ["--etichetta", etichetta]
        self._avvia_processo(cmd, out / f"{self.stem}_link_{stamp}.log", self.w_link_info,
                             al_termine=self._dopo_link, nota=nota)

    def _dopo_link(self):
        etichetta = str(self.w_link_etichetta.value).strip()
        stem = f"{self.stem}_{etichetta}" if etichetta else self.stem
        # i file del linking finiscono accanto ai blob, che non e' detto siano in w_out
        trovato = find_table(Path(str(self.w_blobs_file.value)).parent, stem, "tracks")
        if trovato is not None:
            self.w_tracks_file.value = str(trovato)
            self.w_link_info.value += "\n-> caricabile dal pannello 6"
