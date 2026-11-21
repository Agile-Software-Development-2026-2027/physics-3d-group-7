"""Export completed pipeline data using the existing table writer."""

import time
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from apkit4d.batching.export import save_batch_results
from apkit4d.batching.processor import BatchResult
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.controllers.pipeline_controller import PipelineController
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.models.pipeline_model import PipelineStep, StepStatus
from apkit4d.gui.views.main_window import MainWindow


class BatchController(QObject):
    """Save pipeline results when its Batch stage enters RUNNING."""

    progress_changed = Signal(int, int)

    def __init__(
        self,
        window: MainWindow,
        files: FileController,
        pipeline: PipelineController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._view = window.right_panel.batch_inspector
        self._pipeline = pipeline
        self._source: tuple[Path, int] | None = None
        self._task: int | None = None
        self._batch_started_at: float = 0.0
        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._succeeded)
        self._runner.failed.connect(self._failed)
        self.progress_changed.connect(self._progress)
        pipeline.set_stage_runner(PipelineStep.BATCH, self.run)
        files.loaded.connect(self.set_source)
        files.closed.connect(self.clear_source)
        self._set_enabled()

    def set_source(self, path: Path, source: FrameSource) -> None:
        self._pipeline.reset_pipeline()
        self._source = (path, getattr(source, "channel", 0)) if source.info.n_t > 0 else None
        self._view.output_dir.setText(str(path.parent))
        for field in (self._view.first_frame, self._view.last_frame):
            field.setRange(1, max(1, source.info.n_t))
        self._view.first_frame.setValue(1)
        self._view.last_frame.setValue(max(1, source.info.n_t))
        if self._task is None:
            self._pipeline.clear_batch_status()
        self._set_enabled()

    def clear_source(self) -> None:
        self._pipeline.reset_pipeline()
        self._source = None
        if self._task is None:
            self._pipeline.clear_batch_status()
        self._set_enabled()

    def _set_enabled(self) -> None:
        enabled = self._source is not None and self._task is None
        self._view.setEnabled(enabled)
        button = self._window.right_panel.get_play_button(PipelineStep.BATCH)
        if button is not None:
            button.setEnabled(enabled)

    def run(self) -> None:
        if (
            self._task is not None
            or self._pipeline.model.get_status(PipelineStep.BATCH) != StepStatus.RUNNING
        ):
            return
        try:
            if self._source is None:
                raise ValueError("Open a CZI file before exporting.")
            results = self._pipeline.model.batch_results
            if results is None:
                raise ValueError(
                    "No processed pipeline data available. Detection must provide results before export."
                )
            detections, metadata = results
            path, channel = self._source
            if Path(metadata["czi"]).resolve() != path.resolve() or metadata["channel"] != channel:
                raise ValueError("Processed results do not belong to the current source and channel.")
            if not self._view.output_dir.text().strip():
                raise ValueError("Choose an output folder.")
            first = self._view.first_frame.value() - 1
            last = self._view.last_frame.value() - 1
            if first > last:
                raise ValueError("First frame cannot be greater than last frame.")
            job = partial(
                save_batch_results,
                detections=detections,
                metadata=metadata,
                out_dir=Path(self._view.output_dir.text()),
                fmt=self._view.format.currentText(),
                first=first,
                last=last,
                progress=self.progress_changed.emit,
            )
            self._batch_started_at = time.monotonic()
            self._progress(0, len(detections))
            self._task = self._runner.run(job)
            self._set_enabled()
        except Exception as error:
            self._show_error(error)

    def _progress(self, done: int, total: int) -> None:
        if self._pipeline.model.get_status(PipelineStep.BATCH) != StepStatus.RUNNING:
            return
        elapsed = time.monotonic() - self._batch_started_at if self._batch_started_at else 0.0
        self._pipeline.report_stage_progress(
            PipelineStep.BATCH,
            done=done,
            total=total,
            elapsed_seconds=elapsed,
            item_label="detections",
        )
        self._window.right_panel.set_stats_progress(done, total)

    def _succeeded(self, task: int, result: object) -> None:
        if task != self._task:
            return
        self._task = None
        self._set_enabled()
        if self._pipeline.model.get_status(PipelineStep.BATCH) != StepStatus.RUNNING:
            return
        if not isinstance(result, BatchResult):
            self._show_error(ValueError("Batch processing returned no result."))
            return
        if result.num_blobs == 0:
            message = texts.BATCH_EMPTY.format(frames=result.num_frames, params=result.params_path)
            self._pipeline.report_batch(texts.BATCH_COMPLETE, message, StepStatus.COMPLETED)
            self._window.set_status(message)
            return
        message = texts.BATCH_SAVED.format(
            blobs=result.num_blobs,
            frames=result.num_frames,
            table=result.table_path,
            params=result.params_path,
        )
        self._pipeline.report_batch(texts.BATCH_COMPLETE, message, StepStatus.COMPLETED)
        self._window.set_status(str(result.table_path))

    def _failed(self, task: int, error: object) -> None:
        if task == self._task:
            self._task = None
            self._set_enabled()
            if self._pipeline.model.get_status(PipelineStep.BATCH) == StepStatus.RUNNING:
                self._show_error(error)

    def _show_error(self, error: object) -> None:
        self._task = None
        self._set_enabled()
        self._window.right_panel.bottom_stats.progress.hide()
        message = texts.BATCH_FAILED.format(reason=error)
        self._pipeline.report_batch(texts.BATCH_ERROR_TITLE, message, StepStatus.IDLE)
        self._window.right_panel.bottom_stats.set_expanded(True, animate=False)
        self._window.set_status(message)
