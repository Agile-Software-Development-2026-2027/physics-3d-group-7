"""
io_table.py
===========
Lettura e scrittura delle tabelle di detection e traiettorie, in parquet o csv.

Perche' parquet come default (misurato su Exp-571, 2.56 milioni di blob):

    csv       526 MB    lettura di 4 colonne: 2 s, 82 MB in RAM
    parquet   119 MB    lettura di 4 colonne: 0.1 s, 51 MB in RAM

Il parquet e' colonnare, quindi legge solo le colonne che servono invece dell'intero
file, ed e' in float32: per tabelle da milioni di righe e' la differenza fra caricare
mezzo GB e caricarne 50 MB. Il csv resta disponibile (`--format csv`) per chi deve
aprirle altrove.

`TableWriter` scrive man mano, un blocco alla volta: cosi' il processo che coordina il
batch non tiene in memoria tutti i frame fino alla fine (erano ~700 MB su Exp-571), e
un'interruzione non butta via il lavoro gia' fatto.
"""

from pathlib import Path

import numpy as np
import pandas as pd

FORMATS = ("parquet", "csv")


def _downcast(df: pd.DataFrame) -> pd.DataFrame:
    """float64 -> float32: la precisione di un centroide in µm non ne ha bisogno."""
    cols = {c: "float32" for c in df.columns if df[c].dtype == np.float64}
    return df.astype(cols) if cols else df


def table_path(out_dir, stem: str, suffix: str, fmt: str = "parquet") -> Path:
    return Path(out_dir) / f"{stem}_{suffix}.{fmt}"


def find_table(out_dir, stem: str, suffix: str):
    """Prima parquet, poi csv. None se non c'e' nessuno dei due."""
    for fmt in FORMATS:
        p = table_path(out_dir, stem, suffix, fmt)
        if p.is_file():
            return p
    return None


def read_table(path, columns=None, filtri=None) -> pd.DataFrame:
    """`filtri` in forma pyarrow: [("frame", ">=", 10), ("z_um", "<=", 800), ...].

    Su parquet il filtro viene applicato durante la lettura, quindi le righe escluse non
    entrano mai in memoria: e' il modo di lavorare su un ritaglio senza caricare tutto.
    Su csv si filtra dopo, perche' non c'e' alternativa.
    """
    path = Path(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path, columns=columns, filters=filtri or None)
    df = pd.read_csv(path, usecols=columns)
    for col, op, val in (filtri or []):
        df = df[df[col] >= val] if op == ">=" else df[df[col] <= val]
    return df


def write_table(df: pd.DataFrame, path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".parquet":
        _downcast(df).to_parquet(path, index=False)
    else:
        df.to_csv(path, index=False)
    return path


class TableWriter:
    """Scrittura incrementale: `append` un blocco alla volta, poi `close`.

    In parquet ogni blocco diventa un row group; in csv un'aggiunta in coda. In entrambi
    i casi le righe restano nell'ordine in cui arrivano, che con il batch in parallelo NON
    e' l'ordine dei frame: chi legge ordina (ApKit4D.link lo fa).
    """

    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.unlink(missing_ok=True)
        self._writer = None
        self._fh = None
        self.n_rows = 0

    def append(self, df: pd.DataFrame):
        if df is None or len(df) == 0:
            return
        df = _downcast(df)
        self.n_rows += len(df)
        if self.path.suffix == ".parquet":
            import pyarrow as pa
            import pyarrow.parquet as pq
            table = pa.Table.from_pandas(df, preserve_index=False)
            if self._writer is None:
                self._writer = pq.ParquetWriter(self.path, table.schema, compression="zstd")
            self._writer.write_table(table)
        else:
            header = self._fh is None
            if header:
                self._fh = open(self.path, "w")
            df.to_csv(self._fh, index=False, header=header)

    def close(self):
        if self._writer is not None:
            self._writer.close()
        if self._fh is not None:
            self._fh.close()
        return self.path
