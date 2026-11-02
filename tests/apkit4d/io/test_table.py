"""Unit tests for table I/O operations and TableWriter."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from apkit4d.io.table import (
    FORMATS,
    TableWriter,
    downcast_floats,
    find_table,
    read_table,
    table_path,
    write_table,
)


class TestTableIO:
    def test_downcast_floats(self) -> None:
        """Verify that float64 columns are converted to float32."""
        assert "parquet" in FORMATS and "csv" in FORMATS
        df = pd.DataFrame(
            {
                "frame": [0, 1],
                "x_um": np.array([1.23456789, 2.34567891], dtype=np.float64),
                "label": [1, 2],
            }
        )
        downcasted = downcast_floats(df)
        assert downcasted["x_um"].dtype == np.float32
        assert downcasted["frame"].dtype == int

    def test_table_path_construction(self, tmp_path: Path) -> None:
        """Verify file path construction for tables."""
        p_parquet = table_path(tmp_path, "sample_stem", "blobs", "parquet")
        assert p_parquet == tmp_path / "sample_stem_blobs.parquet"

        p_csv = table_path(tmp_path, "sample_stem", "tracks", "csv")
        assert p_csv == tmp_path / "sample_stem_tracks.csv"

    def test_find_table(self, tmp_path: Path) -> None:
        """Verify finding existing table files prioritizing Parquet."""
        assert find_table(tmp_path, "exp", "blobs") is None

        # Create CSV
        csv_file = tmp_path / "exp_blobs.csv"
        csv_file.touch()
        assert find_table(tmp_path, "exp", "blobs") == csv_file

        # Create Parquet - should take priority over CSV
        parquet_file = tmp_path / "exp_blobs.parquet"
        parquet_file.touch()
        assert find_table(tmp_path, "exp", "blobs") == parquet_file

    def test_csv_write_and_read_with_filters(self, tmp_path: Path) -> None:
        """Verify writing and reading CSV tables with filtering."""
        df = pd.DataFrame(
            {
                "frame": [0, 1, 2, 3],
                "val": [10.0, 20.0, 30.0, 40.0],
                "name": ["a", "b", "c", "d"],
            }
        )
        out_csv = tmp_path / "test.csv"
        written = write_table(df, out_csv)
        assert written.is_file()

        # Read all
        loaded = read_table(out_csv)
        assert len(loaded) == 4

        # Read with column selection
        loaded_sub = read_table(out_csv, columns=["frame", "val"])
        assert list(loaded_sub.columns) == ["frame", "val"]

        # Read with filters
        filtered = read_table(out_csv, filters=[("val", ">=", 20.0), ("val", "<", 40.0)])
        assert len(filtered) == 2
        assert list(filtered["frame"]) == [1, 2]

        # Additional filter operators: <=, >, ==, !=
        filtered_ops = read_table(out_csv, filters=[("frame", "<=", 2), ("frame", ">", 0)])
        assert len(filtered_ops) == 2

        filtered_eq = read_table(out_csv, filters=[("name", "==", "b")])
        assert len(filtered_eq) == 1
        assert filtered_eq.iloc[0]["frame"] == 1

        filtered_ne = read_table(out_csv, filters=[("name", "!=", "b")])
        assert len(filtered_ne) == 3

    def test_parquet_write_and_read(self, tmp_path: Path) -> None:
        """Verify writing and reading Parquet tables."""
        df = pd.DataFrame(
            {
                "frame": [0, 1, 2],
                "z_um": [1.0, 2.0, 3.0],
            }
        )
        out_parquet = tmp_path / "test.parquet"
        write_table(df, out_parquet)
        assert out_parquet.is_file()

        loaded = read_table(out_parquet, columns=["frame", "z_um"])
        assert len(loaded) == 3
        assert list(loaded.columns) == ["frame", "z_um"]

        # Filtering on parquet
        filtered = read_table(out_parquet, filters=[("frame", ">=", 1)])
        assert len(filtered) == 2

    def test_table_writer_csv_incremental(self, tmp_path: Path) -> None:
        """Verify incremental chunk appending for CSV via TableWriter."""
        target = tmp_path / "incremental.csv"
        with TableWriter(target) as writer:
            assert writer.n_rows == 0
            writer.append(None)
            writer.append(pd.DataFrame())
            assert writer.n_rows == 0

            df1 = pd.DataFrame({"frame": [0, 1], "x": [10.0, 20.0]})
            writer.append(df1)
            assert writer.n_rows == 2

            df2 = pd.DataFrame({"frame": [2, 3], "x": [30.0, 40.0]})
            writer.append(df2)
            assert writer.n_rows == 4

        loaded = pd.read_csv(target)
        assert len(loaded) == 4
        assert list(loaded["frame"]) == [0, 1, 2, 3]

    def test_table_writer_parquet_incremental(self, tmp_path: Path) -> None:
        """Verify incremental chunk appending for Parquet via TableWriter."""
        target = tmp_path / "incremental.parquet"
        with TableWriter(target) as writer:
            df1 = pd.DataFrame({"frame": [0, 1], "x": [10.0, 20.0]})
            writer.append(df1)
            df2 = pd.DataFrame({"frame": [2, 3], "x": [30.0, 40.0]})
            writer.append(df2)
            assert writer.n_rows == 4

        loaded = read_table(target)
        assert len(loaded) == 4
        assert list(loaded["frame"]) == [0, 1, 2, 3]

    def test_table_writer_parquet_missing_pyarrow(self, tmp_path: Path) -> None:
        """Verify that missing pyarrow raises ImportError when writing parquet."""
        target = tmp_path / "test_missing.parquet"
        writer = TableWriter(target)
        df = pd.DataFrame({"frame": [0], "x": [1.0]})

        with (
            patch("apkit4d.io.table.pa", None),
            patch("apkit4d.io.table.pq", None),
            pytest.raises(ImportError, match="pyarrow is required"),
        ):
            writer.append(df)
        writer.close()

    def test_table_writer_parquet_mocked(self, tmp_path: Path) -> None:
        """Verify Parquet TableWriter logic when pyarrow is mocked."""
        target = tmp_path / "test_mocked.parquet"
        mock_pa = MagicMock()
        mock_pq = MagicMock()
        mock_table = MagicMock()
        mock_pa.Table.from_pandas.return_value = mock_table

        with (
            patch("apkit4d.io.table.pa", mock_pa),
            patch("apkit4d.io.table.pq", mock_pq),
            TableWriter(target) as writer,
        ):
            df = pd.DataFrame({"frame": [0, 1], "x": [10.0, 20.0]})
            writer.append(df)
            assert writer.n_rows == 2
            mock_pq.ParquetWriter.assert_called_once_with(target, mock_table.schema, compression="zstd")
            mock_writer_instance = mock_pq.ParquetWriter.return_value
            mock_writer_instance.write_table.assert_called_once_with(mock_table)

        mock_writer_instance.close.assert_called_once()
