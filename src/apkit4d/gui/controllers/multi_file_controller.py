from collections.abc import Callable
from contextlib import closing
from datetime import date
from functools import partial
from pathlib import Path
from typing import Any

from PySide6.QtCore import QModelIndex, QObject, Qt, Signal
from PySide6.QtWidgets import QAbstractItemView, QListWidgetItem

from apkit4d.batching.export import save_batch_results
from apkit4d.core.models import DetectionConfig, PreprocessingConfig, RoiConfig, TrackingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.trajectory_detection import detect_sequence
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziSource
from apkit4d.io.session import PrecomputedFrameSource
from apkit4d.tracking.linker import ParticleLinker

_READY_ROLE = Qt.ItemDataRole.UserRole + 1


def _process_recordings(
    recordings: tuple[Path, ...],
    output_dir: Path,
    fmt: str,
    first: int,
    last: int,
    shape: tuple[int, int, int],
    channel: int,
    roi: RegionOfInterest | None,
    preproc: PreprocessingConfig,
    detection: DetectionConfig,
    tracking: TrackingConfig | None,
    update: Callable[[int, str, str], None],
) -> int:
    """Process each recording with the same pipeline settings.

    Detection and tracking use the full recording. The frame range limits the export.
    Each recording gets its own output directory, including when input names match.

    Args:
        recordings: CZI paths in the order they appear in the batch.
        output_dir: Existing folder in which to create the batch output directory.
        fmt: Table format for exported detections and tracks.
        first: First frame to export, as a zero-based inclusive index.
        last: Last frame to export, as a zero-based inclusive index.
        shape: Required volume dimensions in Z, Y, X order.
        channel: Zero-based channel index to read from every recording.
        roi: Shared region in physical coordinates, or None to use the full volume.
        preproc: Preprocessing settings for all recordings.
        detection: Blob detection settings for all recordings.
        tracking: Trajectory linking settings, or None to skip tracking.
        update: Callback receiving the zero-based row index, status message, and
            saved result path. The path is empty until export succeeds.

    Returns:
        Number of recordings whose results were saved successfully.
    """
    folder_name = f"apkit4d-batch-{date.today().isoformat()}"
    run_dir = output_dir / folder_name
    run_number = 1
    while True:
        try:
            run_dir.mkdir()
        except FileExistsError:
            run_number += 1
            run_dir = output_dir / f"{folder_name}-{run_number}"
        else:
            break
    completed = 0
    for row, path in enumerate(recordings):
        update(row, texts.MULTI_FILE_OPENING, "")
        try:
            with closing(CziSource(path, channel=channel)) as source:
                info = source.info
                if (info.n_z, info.n_y, info.n_x) != shape:
                    raise ValueError(texts.MULTI_FILE_DIMENSION_ERROR.format(shape=shape))
                if last >= info.n_t:
                    raise ValueError(
                        texts.MULTI_FILE_FRAME_LIMIT_ERROR.format(last=last + 1, frames=info.n_t)
                    )
                data = detect_sequence(
                    source,
                    preproc,
                    detection,
                    RoiConfig().with_region(roi),
                    progress_callback=lambda done, total, row=row: update(
                        row, texts.MULTI_FILE_DETECTING.format(done=done, total=total), ""
                    ),
                )
            tracks = None
            if tracking is not None:
                update(row, texts.MULTI_FILE_TRACKING_STATUS, "")
                tracks = ParticleLinker(tracking).link(data.detections, dt_s=data.dt_s).tracks
            update(row, texts.MULTI_FILE_SAVING, "")
            result = save_batch_results(
                data.detections,
                data.metadata,
                run_dir / str(row + 1),
                fmt,
                first,
                last,
                progress=lambda _done, _total: None,
                tracks=tracks,
                tracking_config=tracking,
            )
        except Exception as error:
            update(row, texts.MULTI_FILE_RECORDING_ERROR.format(error=error), "")
        else:
            completed += 1
            update(row, texts.MULTI_FILE_SAVED, str(result.params_path))
    return completed


class MultiFileController(QObject):
    """Connect the File menu and the batch panel to background processing.

    The active recording supplies the reference dimensions, channel, and ROI.
    The controller reads the current pipeline and export settings when Run is clicked.

    Args:
        window: Main window with the batch controls and export settings.
        files: Controller that opens the reference recording.
        pipeline: Model holding the current analysis parameters.
        current_roi: Function returning the active ROI, if one is set.
        parent: Qt parent that owns this controller.
        show_roi: Function applying the inherited ROI to a replacement recording.

    Signals:
        recording_updated: Carries the row index, status, and optional result path.
    """

    recording_updated = Signal(int, str, str)

    def __init__(
        self,
        window: MainWindow,
        files: FileController,
        pipeline: PipelineModel,
        parent: QObject,
        show_roi: Callable[[RegionOfInterest], None],
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._panel = window.multi_file_panel
        self._export = window.right_panel.batch_inspector
        self._files = files
        self._pipeline = pipeline
        self._current_roi = self._pipeline.get_roi_params().region
        self._show_roi = show_roi
        # Store the new reference path, the row to remove if any, and the function
        # that restores the previous settings.
        self._replacement: tuple[Path, int | None, Callable[[], None]] | None = None
        # The active CZI path, if it can be used as the batch reference
        self._reference: Path | None = None
        # Paths selected via Open files while the first recording loads
        self._pending: tuple[Path, ...] = ()
        # Paths queued for processing when the user clicks Run
        self._recordings: list[Path] = []
        # ID of the running batch, or None when idle
        self._task: int | None = None

        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._finished)
        self._runner.failed.connect(self._failed)
        self.recording_updated.connect(self._show_recording_status)
        window.files_selected.connect(self._open_files)
        window.files_added.connect(self._add_files)
        window.file_opened.connect(self._clear_pending)
        window.results_opened.connect(self._clear_pending)
        files.loaded.connect(self._loaded)
        files.closed.connect(self._closed)
        files.open_failed.connect(self._open_failed)
        self._panel.run.clicked.connect(self._run)
        self._panel.recordings.itemDoubleClicked.connect(self._open_result)
        self._panel.recordings.itemSelectionChanged.connect(self._refresh)
        self._panel.recordings.model().rowsMoved.connect(self._reorder_recording)
        self._panel.remove.clicked.connect(self._remove_selected)

    def _open_files(self, paths: list[Path]) -> None:
        if not paths or self._task is not None:
            return
        # Keep the existing queue until the new reference opens successfully.
        resolved_paths = [path.resolve() for path in paths]
        self._pending = tuple(dict.fromkeys(resolved_paths))
        self._refresh()
        self._files.open_file(self._pending[0])

    def _add_files(self, paths: list[Path]) -> None:
        """Add selected recordings to the batch queue.

        Args:
            paths: Paths selected via Add files.
        """
        if self._reference is None or self._pending or self._task is not None or not paths:
            return
        # When starting a queue with Add files, include the active recording.
        if not self._recordings:
            self._recordings.append(self._reference)
        new_paths = [path.resolve() for path in paths]
        all_paths = self._recordings + new_paths
        self._recordings = list(dict.fromkeys(all_paths))
        self._show_queue()

    def _loaded(self, path: Path, source: FrameSource) -> None:
        """Update the reference and confirm a pending selection when its first file loads.

        Args:
            path: Path to the newly opened recording.
            source: Open recording that supplies the frame count.
        """
        path = path.resolve()
        self._reference = (
            path if path.is_file() and path.suffix.lower() == ".czi" and source.info.n_t else None
        )
        if self._pending and path == self._pending[0]:
            self._recordings = list(self._pending)
            self._pending = ()
            self._show_queue()
        # Restore settings after switching references, then remove the old row if requested
        if self._replacement is not None and path == self._replacement[0]:
            _, row, restore_settings = self._replacement
            self._replacement = None
            restore_settings()
            if row is not None:
                self._remove_row(row)
        self._mark_active_recording()
        self._refresh()

    def _closed(self) -> None:
        self._reference = None
        # Clear the highlight for the closed recording
        self._mark_active_recording()
        self._refresh()

    def _open_failed(self, path: Path) -> None:
        if self._pending and path == self._pending[0]:
            self._clear_pending()
        if self._replacement is not None and path == self._replacement[0]:
            self._clear_pending()
            self._panel.status.setText(texts.MULTI_FILE_REPLACEMENT_ERROR)

    def _clear_pending(self) -> None:
        self._pending = ()
        self._replacement = None
        self._refresh()

    def _show_queue(self) -> None:
        """Rebuild the visible queue and mark every recording as ready."""
        self._panel.recordings.clear()
        for row, path in enumerate(self._recordings):
            self._panel.recordings.addItem(path.name)
            self._show_recording_status(row, texts.MULTI_FILE_READY, "")
        self._panel.status.clear()
        self._window.show_multi_file_panel()
        self._refresh()

    def _refresh(self) -> None:
        """Enable controls based on whether a reference is loaded and a batch can start."""
        # Allow queue changes when no batch is running and no reference is loading
        idle = self._task is None and not self._pending and self._replacement is None
        self._window.open_files_action.setEnabled(idle)
        self._window.add_files_action.setEnabled(idle and self._reference is not None)
        self._panel.run.setEnabled(idle and self._reference is not None and bool(self._recordings))
        self._panel.tracking.setEnabled(idle)
        self._panel.remove.setEnabled(
            idle and len(self._recordings) > 1 and bool(self._panel.recordings.selectedItems())
        )
        self._panel.recordings.setDragDropMode(
            QAbstractItemView.DragDropMode.InternalMove if idle else QAbstractItemView.DragDropMode.NoDragDrop
        )

    def _reorder_recording(
        self,
        _source_parent: QModelIndex,
        first: int,
        last: int,
        _target_parent: QModelIndex,
        destination: int,
    ) -> None:
        """Keep the batch order in sync with the list.

        Args:
            _source_parent: Parent index from Qt, unused.
            first: First row to move.
            last: Last row to move, inclusive.
            _target_parent: Parent index from Qt, unused.
            destination: Insertion row before the move.
        """
        moved = self._recordings[first : last + 1]
        del self._recordings[first : last + 1]
        # The target row number is smaller after removing rows above it
        if destination > last:
            destination -= len(moved)
        self._recordings[destination:destination] = moved

    def _remove_selected(self) -> None:
        """Remove the selected input from the queue and keep the other rows intact."""
        if not self._panel.remove.isEnabled():
            return
        item = self._panel.recordings.selectedItems()[0]
        row = self._panel.recordings.row(item)
        if self._recordings[row] == self._reference:
            # Use the row below if there is one. Otherwise, use the row above
            next_row = row + 1 if row + 1 < len(self._recordings) else row - 1
            next_path = self._recordings[next_row]
            self._open_reference(next_path, row_to_remove=row)
            # _loaded() removes the row after the new recording opens
            return
        self._remove_row(row)

    def _open_reference(self, path: Path, *, row_to_remove: int | None = None) -> None:
        """Open a reference and preserve the current batch settings.

        Args:
            path: Recording to open as the new reference.
            row_to_remove: Queue row to remove after opening succeeds, if any.
        """
        self._replacement = (path, row_to_remove, self._capture_settings())
        self._refresh()
        self._files.open_file(path)

    def _capture_settings(self) -> Callable[[], None]:
        """Capture settings before loading a recording resets the controls.

        Returns:
            A callback that reapplies the captured pipeline, ROI, and export settings.
        """
        steps = (PipelineStep.PREPROCESSING, PipelineStep.DETECTION, PipelineStep.TRACKING)
        params = {step: self._pipeline.get_step_params(step) for step in steps}
        roi = self._current_roi
        folder = self._export.output_dir.text()
        fmt = self._export.format.currentText()
        first = self._export.first_frame.value()
        last = self._export.last_frame.value()

        # Keep these values so we can restore them once the replacement recording opens
        return partial(
            self._restore_settings,
            params=params,
            roi=roi,
            folder=folder,
            fmt=fmt,
            first=first,
            last=last,
        )

    def _restore_settings(
        self,
        params: dict[PipelineStep, dict[str, Any]],
        roi: RegionOfInterest | None,
        folder: str,
        fmt: str,
        first: int,
        last: int,
    ) -> None:
        """Apply the previous settings to the newly loaded recording.

        Args:
            params: Saved parameter values for each analysis step.
            roi: Saved crop, if one was set.
            folder: Export output folder.
            fmt: Export table format.
            first: First frame to export, as shown in the GUI.
            last: Last frame to export, as shown in the GUI.
        """
        for step, step_params in params.items():
            self._pipeline.update_step_params(step, **step_params)
        if roi is not None:
            self._pipeline.update_step_params(PipelineStep.ROI, **roi.to_dict())
            self._show_roi(roi)
        self._export.output_dir.setText(folder)
        self._export.format.setCurrentText(fmt)
        self._export.first_frame.setValue(first)
        self._export.last_frame.setValue(last)

    def _remove_row(self, row: int) -> None:
        self._recordings.pop(row)
        self._panel.recordings.takeItem(row)
        self._panel.status.clear()
        self._refresh()

    def _run(self) -> None:
        """Read settings on the GUI thread and submit the batch to the worker."""
        source = self._files.source
        if source is None or not self._panel.run.isEnabled():
            return
        folder = self._export.output_dir.text().strip()
        if not folder:
            self._panel.status.setText(texts.MULTI_FILE_OUTPUT_ERROR)
            return

        output_dir = Path(folder).expanduser().resolve()
        if not output_dir.is_dir():
            self._panel.status.setText(texts.MULTI_FILE_OUTPUT_ERROR)
            return
        first = self._export.first_frame.value() - 1
        last = self._export.last_frame.value() - 1
        if first > last:
            self._panel.status.setText(texts.MULTI_FILE_FRAME_ORDER_ERROR)
            return
        preproc = self._pipeline.get_preproc_params()
        if not preproc.normalization_enabled:
            self._panel.status.setText(texts.DETECTION_REQUIRES_NORMALIZATION)
            return
        detection = DetectionConfig(**self._pipeline.get_step_params(PipelineStep.DETECTION))
        tracking = (
            TrackingConfig(**self._pipeline.get_step_params(PipelineStep.TRACKING))
            if self._panel.tracking.isChecked()
            else None
        )
        info = source.info
        job = partial(
            _process_recordings,
            tuple(self._recordings),
            output_dir,
            self._export.format.currentText(),
            first,
            last,
            (info.n_z, info.n_y, info.n_x),
            getattr(source, "channel", 0),
            self._current_roi,
            preproc,
            detection,
            tracking,
            self.recording_updated.emit,
        )
        for row in range(len(self._recordings)):
            self._show_recording_status(row, texts.MULTI_FILE_QUEUED, "")
        self._panel.status.setText(texts.MULTI_FILE_PROCESSING)
        self._task = self._runner.run(job)
        self._refresh()

    def _show_recording_status(self, row: int, status: str, result: str) -> None:
        path = self._recordings[row]
        item = self._panel.recordings.item(row)
        item.setText(f"{path.name}  -  {status}" + (f"  -  {result}" if result else ""))
        item.setData(Qt.ItemDataRole.UserRole, result or None)
        ready = status == texts.MULTI_FILE_READY
        item.setData(_READY_ROLE, ready)
        tooltip = f"{path}\n{result or status}"
        if result:
            tooltip += f"\n{texts.MULTI_FILE_OPEN_RESULT_HINT}"
        elif ready:
            tooltip += f"\n{texts.MULTI_FILE_OPEN_RECORDING_HINT}"
        item.setToolTip(tooltip)
        self._mark_active_result(item)

    def _open_result(self, item: QListWidgetItem) -> None:
        """Open a queued recording or its saved result after a double-click.

        Args:
            item: List item carrying the result path, if available.
        """
        if self._task is not None or self._pending or self._replacement is not None:
            return
        result = item.data(Qt.ItemDataRole.UserRole)
        if result:
            self._files.open_results(Path(result))
        elif item.data(_READY_ROLE):
            row = self._panel.recordings.row(item)
            self._open_reference(self._recordings[row])

    def _mark_active_recording(self) -> None:
        for row in range(self._panel.recordings.count()):
            self._mark_active_result(self._panel.recordings.item(row))

    def _mark_active_result(self, item: QListWidgetItem) -> None:
        """Highlight a row if its saved result is open.

        Args:
            item: List item to compare against the active result.
        """
        source = self._files.source
        result = item.data(Qt.ItemDataRole.UserRole)
        active = (
            isinstance(source, PrecomputedFrameSource)
            and source.params_path is not None
            and result == str(source.params_path)
        )
        font = item.font()
        font.setBold(active)
        item.setFont(font)

    def _finished(self, task: int, completed: int) -> None:
        if task == self._task:
            self._task = None
            self._panel.status.setText(
                texts.MULTI_FILE_COMPLETE.format(completed=completed, total=len(self._recordings))
            )
            self._refresh()

    def _failed(self, task: int, error: Exception) -> None:
        if task == self._task:
            self._task = None
            for row in range(len(self._recordings)):
                self._show_recording_status(row, texts.MULTI_FILE_FAILED, "")
            self._panel.status.setText(texts.MULTI_FILE_START_ERROR.format(error=error))
            self._refresh()
