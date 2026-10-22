"""
watchdog.py
===========
Sorveglia il thread grafico e registra i blocchi.

Serve perche' un'interfaccia che "non risponde" puo' avere cause molto diverse (lettura
da disco, calcolo, rendering, attesa di un lock) e indovinare non porta lontano: misurato
a tavolino, qui il calcolo dei blob lascia il thread principale reattivo al 98 % e nessuna
operazione su napari supera il secondo. Il blocco va quindi catturato mentre avviene.

Come funziona: un QTimer sul thread grafico aggiorna un battito ogni 100 ms. Un thread
separato lo controlla: se il battito e' fermo da piu' di `soglia_s`, significa che il
thread grafico e' occupato e non puo' rispondere. A quel punto il thread di controllo
preleva lo stack del thread grafico — cioe' la riga di codice in cui e' fermo — e lo
scrive nel log.

Uso:  python -m ApKit4D --diagnostica
Log:  ApKit4D_blocchi.log nella cartella del progetto
"""

import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path

from qtpy.QtCore import QTimer


class Sorvegliante:
    def __init__(self, log: Path, soglia_s: float = 1.0, intervallo_ms: int = 100):
        self.log = Path(log)
        self.soglia = soglia_s
        self.battito = time.monotonic()
        self.id_grafico = threading.get_ident()
        self.n_blocchi = 0
        self._stop = threading.Event()

        self.log.write_text(f"# blocchi dell'interfaccia oltre {soglia_s:g} s — "
                            f"avvio {datetime.now():%Y-%m-%d %H:%M:%S}\n")
        self.timer = QTimer()
        self.timer.setInterval(intervallo_ms)
        self.timer.timeout.connect(self._batti)
        self.timer.start()
        self.thread = threading.Thread(target=self._controlla, daemon=True)
        self.thread.start()

    def _batti(self):
        self.battito = time.monotonic()

    def _controlla(self):
        gia_segnalato = False
        while not self._stop.wait(0.1):
            fermo_da = time.monotonic() - self.battito
            if fermo_da > self.soglia and not gia_segnalato:
                self._registra(fermo_da)
                gia_segnalato = True
            elif fermo_da <= self.soglia:
                gia_segnalato = False

    def _registra(self, fermo_da):
        self.n_blocchi += 1
        frame = sys._current_frames().get(self.id_grafico)
        pila = "".join(traceback.format_stack(frame)) if frame else "(stack non disponibile)\n"
        # le righe dell'app sono quelle che interessano davvero
        nostre = [r for r in pila.splitlines() if "/ApKit4D/" in r]
        with open(self.log, "a") as fh:
            fh.write(f"\n{'=' * 70}\n{datetime.now():%H:%M:%S} — bloccato da {fermo_da:.1f} s\n")
            if nostre:
                fh.write("righe di ApKit4D coinvolte:\n" + "\n".join(nostre) + "\n")
            fh.write("stack completo del thread grafico:\n" + pila)

    def ferma(self):
        self._stop.set()
        self.timer.stop()
