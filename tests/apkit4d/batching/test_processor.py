"""Unit tests for BatchProcessor coordinator, BatchResult, and execution engine."""

import dataclasses
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

import apkit4d.batching.processor as batch_alias
from apkit4d.batching.processor import (
    BatchProcessor,
    BatchResult,
    run,
    run_batch,
    stem_of,
)
from apkit4d.blob_detection import BlobParams
from apkit4d.core.models import BatchConfig
from apkit4d.io.czi import CziInfo, CziSource
from apkit4d.preprocessing import PreprocParams


class TestBatchProcessor:
    @pytest.fixture
    def mock_czi_file(self, tmp_path: Path) -> Path:
        """Create a mock acquisition file path."""
        file_path = tmp_path / "Experiment 583 Lightfield.czi"
        file_path.touch()
        return file_path

    @pytest.fixture
    def mock_source(self, mock_czi_file: Path) -> MagicMock:
        """Create a mock CziSource returning 3D volumes with synthetic blobs."""
        src = MagicMock(spec=CziSource)
        src.path = mock_czi_file
        src.channel = 0
        src.info = CziInfo(
            path=str(mock_czi_file),
            n_t=4,
            n_z=10,
            n_y=20,
            n_x=20,
            n_c=1,
            dtype="uint16",
            px_size_x=1.0,
            px_size_y=1.0,
            px_size_z=1.0,
            dt_s=0.5,
            dt_source="test",
        )
        # Synthetic frame volume with a distinct blob
        vol = np.zeros((10, 20, 20), dtype=np.uint16)
        vol[3:7, 8:13, 8:13] = 25000
        src.read.return_value = vol
        return src

    def test_stem_of(self) -> None:
        """Verify stem_of sanitizes paths and replaces spaces with underscores."""
        assert stem_of("data/raw/Experiment 583.czi") == "Experiment_583"
        assert stem_of(Path("/path/to/Sample_Acquisition.czi")) == "Sample_Acquisition"

    def test_batch_result_frozen(self, tmp_path: Path) -> None:
        """Verify BatchResult immutability."""
        res = BatchResult(
            table_path=tmp_path / "t.csv",
            params_path=tmp_path / "p.json",
            num_blobs=10,
            num_frames=2,
            metadata={"test": 1},
        )
        assert res.num_blobs == 10
        with pytest.raises(dataclasses.FrozenInstanceError):
            res.num_blobs = 20  # type: ignore[misc]

    def test_batch_processor_sync_execution(self, mock_source: MagicMock, tmp_path: Path) -> None:
        """Verify BatchProcessor sequential execution end-to-end."""
        out_dir = tmp_path / "processed"
        config = BatchConfig(workers=1, chunk_size=2, output_format="csv")
        bp = BlobParams(threshold=0.05, min_volume_um3=1.0)
        pp = PreprocParams()

        progress_calls = []

        def on_progress(done: int, total: int) -> None:
            progress_calls.append((done, total))

        processor = BatchProcessor(config=config, preproc_params=pp, blob_params=bp)
        result = processor.process(
            czi=mock_source,
            channel=0,
            t0=0,
            t1=2,
            out_dir=out_dir,
            progress_callback=on_progress,
        )

        assert isinstance(result, BatchResult)
        assert result.table_path.is_file()
        assert result.params_path.is_file()
        assert result.num_frames == 3
        assert len(progress_calls) > 0
        assert progress_calls[-1] == (3, 3)

        # Check output table
        table_df = pd.read_csv(result.table_path)
        assert "frame" in table_df.columns
        assert "t_s" in table_df.columns
        assert "z_um" in table_df.columns

        # Check metadata json
        meta = json.loads(result.params_path.read_text())
        assert meta["t0"] == 0
        assert meta["t1"] == 2
        assert meta["format"] == "csv"
        assert meta["formato"] == "csv"  # Legacy compatibility
        assert meta["sorted_by_frame"] is False
        assert meta["ordinato_per_frame"] is False  # Legacy compatibility
        assert "info" in meta
        assert "preproc" in meta
        assert "blob" in meta

    def test_batch_processor_path_input(
        self, mock_czi_file: Path, mock_source: MagicMock, tmp_path: Path
    ) -> None:
        """Verify BatchProcessor handles Path input and closes instantiated CziSource."""
        out_dir = tmp_path / "output_path_test"  # Mario's beloved way of concatenating strings
        config = BatchConfig(workers=1, chunk_size=2, output_format="csv")
        processor = BatchProcessor(config=config)

        with patch("apkit4d.batching.processor.CziSource", return_value=mock_source):
            res = processor.run(mock_czi_file, out_dir=out_dir, t0=0, t1=1)
            assert res.num_frames == 2
            mock_source.close.assert_called_once()

    def test_batch_processor_empty_range(self, mock_source: MagicMock, tmp_path: Path) -> None:
        """Verify handling when requested frame range is empty (t0 > t1)."""
        config = BatchConfig(workers=1, output_format="csv")
        processor = BatchProcessor(config=config)
        result = processor.process(mock_source, t0=5, t1=2, out_dir=tmp_path)
        assert result.num_frames == 0
        assert result.num_blobs == 0

    def test_run_batch_convenience_function(self, mock_source: MagicMock, tmp_path: Path) -> None:
        """Verify run_batch top-level convenience function."""
        config = BatchConfig(workers=1, output_format="csv")
        result = run_batch(mock_source, config=config, t0=0, t1=0, out_dir=tmp_path)
        assert result.num_frames == 1
        assert result.table_path.is_file()

    def test_run_legacy_compatible_function(self, mock_source: MagicMock, tmp_path: Path) -> None:
        """Verify run legacy-compatible function returns Path."""
        out_table = run(
            mock_source,
            workers=1,
            chunk=2,
            fmt="csv",
            t0=0,
            t1=1,
            out_dir=tmp_path,
        )
        assert isinstance(out_table, Path)
        assert out_table.is_file()

    def test_batch_processor_parallel_path(self, mock_source: MagicMock, tmp_path: Path) -> None:
        """Verify multi-worker parallel submission path."""
        config = BatchConfig(workers=2, chunk_size=1, output_format="csv")
        processor = BatchProcessor(config=config)

        fake_detection = pd.DataFrame(
            {
                "frame": [0],
                "label": [1],
                "z": [1.0],
                "y": [2.0],
                "x": [3.0],
                "z_um": [1.0],
                "y_um": [2.0],
                "x_um": [3.0],
                "volume_um3": [10.0],
                "n_voxels": [5],
                "z_extent": [2],
                "response": [0.5],
                "peak": [1.0],
                "mean_intensity": [100.0],
                "max_intensity": [200.0],
            }
        )

        with (
            patch("apkit4d.batching.processor.cap_workers", return_value=(2, "mocked")),
            patch("apkit4d.batching.processor.ProcessPoolExecutor") as mock_executor_cls,
        ):
            mock_executor = MagicMock()
            mock_executor_cls.return_value.__enter__.return_value = mock_executor

            future0 = MagicMock()
            future0.result.return_value = [fake_detection]
            future1 = MagicMock()
            future1.result.return_value = [fake_detection]

            mock_executor.submit.side_effect = [future0, future1]

            with patch("apkit4d.batching.processor.as_completed", return_value=[future0, future1]):
                result = processor.process(mock_source, t0=0, t1=1, out_dir=tmp_path)
                assert result.num_frames == 2
                assert result.num_blobs == 2

    def test_apkit4d_batch_alias_matches(self) -> None:
        """Verify apkit4d.batch single-file alias re-exports batching symbols."""
        assert batch_alias.BatchProcessor is BatchProcessor
        assert batch_alias.BatchResult is BatchResult
        assert batch_alias.run is run
        assert batch_alias.run_batch is run_batch
        assert batch_alias.BatchConfig is BatchConfig
