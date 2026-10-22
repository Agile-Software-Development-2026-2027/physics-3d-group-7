"""
params.py
=========
Persistenza dei parametri per file (recuperato da app_prototipo/app_lib/io_utils.py):
riaprendo lo stesso .czi si riparte dall'ultima configurazione usata.

    data/app_params.json   { "<stem>": {"channel": 0, "t0": 0, "t1": 99,
                                         "preproc": {...}, "blob": {...}} }
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_RAW = BASE_DIR / "data" / "raw"
DATA_OUT = BASE_DIR / "data" / "processed"
PARAMS_FILE = BASE_DIR / "data" / "app_params.json"


def stem_of(czi_path) -> str:
    return Path(czi_path).stem.replace(" ", "_")


def list_czis():
    return sorted(DATA_RAW.glob("*.czi"))


def load(stem: str) -> dict:
    if PARAMS_FILE.exists():
        try:
            return json.loads(PARAMS_FILE.read_text()).get(stem, {})
        except json.JSONDecodeError:
            return {}
    return {}


def save(stem: str, entry: dict):
    PARAMS_FILE.parent.mkdir(parents=True, exist_ok=True)
    allp = {}
    if PARAMS_FILE.exists():
        try:
            allp = json.loads(PARAMS_FILE.read_text())
        except json.JSONDecodeError:
            allp = {}
    allp[stem] = entry
    tmp = PARAMS_FILE.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(allp, indent=2))
    tmp.replace(PARAMS_FILE)  # scrittura atomica: un crash a meta' non corrompe il file
