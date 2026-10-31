"""Table I/O operations for particle detection and trajectory tracking datasets.

Provides reading, writing, and streaming table appenders for Parquet and CSV formats.
Parquet is the preferred format for large datasets due to columnar storage and compression.
CSV remains supported for compatibility and external viewing.

RefactorNote:
    Refactored from `io_table.py`.
    Most italian comments where trsnslated to English.
    We stuck with pyarrow for Parquet support since it seems teh best option, an optioanl alternative
    may be Polars that has the "backend" writte in Rust.
    The only problem it may be taht Polars does not support appendinf stuff only writing whole parquet,
    from a fast research at least.
"""

from pathlib import Path
from typing import Any, Final, TextIO

import numpy as np
import pandas as pd

try:
    import pyarrow as pa
    import pyarrow.parquet as pq
except ImportError:
    pa = None
    pq = None

FORMATS: Final[tuple[str, ...]] = ("parquet", "csv")


def downcast_floats(df: pd.DataFrame) -> pd.DataFrame:
    """Downcast 64-bit float columns to 32-bit floats.

    Centroid and volume precision in micrometers does not require float64,
    cutting memory consumption in half.

    Args:
        df: Input DataFrame.

    Returns:
        DataFrame with float64 columns converted to float32.

    RefactorNote:
        Refactored from `_downcast` from legacy `io_table.py`.
    """
    cols = {col: "float32" for col in df.columns if df[col].dtype == np.float64}
    return df.astype(cols) if cols else df


def table_path(out_dir: str | Path, stem: str, suffix: str, fmt: str = "parquet") -> Path:
    """Construct destination file path for a table.

    Args:
        out_dir: Destination directory.
        stem: Dataset identifier / base name.
        suffix: Table suffix (e.g., 'blobs', 'tracks').
        fmt: File format extension ('parquet' or 'csv').

    Returns:
        Constructed Path object.
    """
    return Path(out_dir) / f"{stem}_{suffix}.{fmt}"


def find_table(out_dir: str | Path, stem: str, suffix: str) -> Path | None:
    """Locate an existing table file, prioritizing Parquet over CSV.

    Args:
        out_dir: Directory to search.
        stem: Dataset identifier / base name.
        suffix: Table suffix (e.g., 'blobs', 'tracks').

    Returns:
        Path to existing file, or None if neither format exists.
    """
    for fmt in FORMATS:
        target = table_path(out_dir, stem, suffix, fmt)
        if target.is_file():
            return target
    return None


def read_table(
    path: str | Path,
    columns: list[str] | None = None,
    filters: list[tuple[str, str, Any]] | None = None,
) -> pd.DataFrame:
    """Read a table from Parquet or CSV with optional column and row filtering.

    For Parquet files, row filtering is pushed down to pyarrow when available,
    minimizing memory usage. For CSV, filters are applied post-reading.

    Args:
        path: Path to table file.
        columns: List of column names to load.
        filters: Row filters in form [(col, op, val), ...]. Supported ops: '>=', '<=', '>', '<', '==', '!='.

    Returns:
        Loaded DataFrame.
    """
    file_path = Path(path)
    active_filters = filters or []

    if file_path.suffix == ".parquet":
        try:
            return pd.read_parquet(file_path, columns=columns, filters=active_filters or None)
        except Exception:
            # Fallback if pyarrow filter pushdown is unavailable or unsupported
            df = pd.read_parquet(file_path, columns=columns)
    else:
        df = pd.read_csv(file_path, usecols=columns)

    for col, op, val in active_filters:
        if op == ">=":
            df = df[df[col] >= val]
        elif op == "<=":
            df = df[df[col] <= val]
        elif op == ">":
            df = df[df[col] > val]
        elif op == "<":
            df = df[df[col] < val]
        elif op == "==":
            df = df[df[col] == val]
        elif op == "!=":
            df = df[df[col] != val]

    return df


def write_table(df: pd.DataFrame, path: str | Path) -> Path:
    """Write an entire DataFrame to a Parquet or CSV table file.

    Args:
        df: DataFrame to save.
        path: Destination file path.

    Returns:
        Destination Path object.
    """
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix == ".parquet":
        downcast_floats(df).to_parquet(target, index=False)
    else:
        df.to_csv(target, index=False)
    return target


class TableWriter:
    """Incremental table writer appending batches chunk by chunk.

    For Parquet, each appended batch becomes a row group.
    For CSV, chunks are appended to the stream with a single initial header.

    RefactorNote:
        Refactored from `TableWriter` from legacy `io_table.py`.
        Added context manager support and explicit resource tracking.
    """

    def __init__(self, path: str | Path) -> None:
        """Initialize writer with target destination file path.

        Args:
            path: Destination file path.
        """
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.unlink(missing_ok=True)
        self._writer: Any | None = None
        self._fh: TextIO | None = None
        self._n_rows: int = 0

    @property
    def n_rows(self) -> int:
        """Total number of rows written so far."""
        return self._n_rows

    def append(self, df: pd.DataFrame | None) -> None:
        """Append a batch of rows to the destination table.

        Args:
            df: DataFrame batch to append.
        """
        if df is None or len(df) == 0:
            return

        downcasted = downcast_floats(df)
        self._n_rows += len(downcasted)

        if self.path.suffix == ".parquet":
            if pa is None or pq is None:
                raise ImportError(
                    "pyarrow is required to write parquet tables. Install pyarrow or use CSV format."
                )

            table = pa.Table.from_pandas(downcasted, preserve_index=False)
            if self._writer is None:
                self._writer = pq.ParquetWriter(self.path, table.schema, compression="zstd")
            self._writer.write_table(table)
        else:
            is_header_needed = self._fh is None
            if is_header_needed:
                self._fh = open(self.path, "w", encoding="utf-8")  # noqa: SIM115
            downcasted.to_csv(self._fh, index=False, header=is_header_needed)

    def close(self) -> Path:
        """Close open file handles and flush written data.

        Returns:
            Path of the completed table file.
        """
        if self._writer is not None:
            self._writer.close()
            self._writer = None
        if self._fh is not None:
            self._fh.close()
            self._fh = None
        return self.path

    def __enter__(self) -> TableWriter:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()
