"""
roi_formati.py
==============
Conversione fra due modi di scrivere la stessa ROI.

Qui dentro ROI e frame sono indici che partono da 0, con estremi inclusi
(z0..z1, y0..y1, x0..x1, t0..t1). Diversi programmi di analisi di immagini usano invece
una notazione a riquadro con origine e dimensioni, e numerano piani e frame a partire
da 1:

    riquadro:  x, y, larghezza, altezza   — angolo in alto a sinistra, in pixel, da 0
    piani:     "20-60"                    — slice Z numerate da 1, estremi inclusi
    frame:     "1-600"                    — volumi numerati da 1, estremi inclusi

Serve per ripetere qui un'analisi impostata altrove (o viceversa) senza rifare i conti a
mano, che e' un'ottima fonte di errori da un indice. Verificato sui dati del progetto: un
riquadro 106, 106, 300, 300 con piani 20-60 e frame 1-600 corrisponde a x e y 106-405,
z 19-59, frame 0-599.
"""

import re

_NUM = r"[-+]?\d+"


def parse_bounds(text):
    """'106, 106, 300, 300' (x, y, larghezza, altezza) -> (x0, x1, y0, y1), indici da 0."""
    n = [int(v) for v in re.findall(_NUM, str(text))]
    if len(n) != 4:
        raise ValueError("servono quattro numeri: x, y, larghezza, altezza")
    x, y, w, h = n
    if w <= 0 or h <= 0:
        raise ValueError("larghezza e altezza devono essere positive")
    return x, x + w - 1, y, y + h - 1


def format_bounds(x0, x1, y0, y1):
    return f"{x0}, {y0}, {x1 - x0 + 1}, {y1 - y0 + 1}"


def parse_range_1based(text):
    """'20-60' (o '20') -> (19, 59): estremi inclusi, riportati a indici da 0."""
    # solo cifre: il '-' qui separa gli estremi, non e' un segno (in '25-45' il secondo
    # numero e' 45, non -45)
    n = [int(v) for v in re.findall(r"\d+", str(text))]
    if not n:
        raise ValueError("intervallo vuoto")
    a = n[0]
    b = n[1] if len(n) > 1 else n[0]
    if a < 1 or b < a:
        raise ValueError("intervallo non valido: i piani e i frame si contano da 1")
    return a - 1, b - 1


def format_range_1based(a0, b0):
    return f"{a0 + 1}-{b0 + 1}"
