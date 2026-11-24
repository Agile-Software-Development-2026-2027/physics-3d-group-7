from collections.abc import Callable
from contextlib import closing
from datetime import date
from functools import partial
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from apkit4d.batching.export import save_batch_results
from apkit4d.core.models import DetectionConfig, PreprocessingConfig, TrackingConfig
from apkit4d.core.roi import RegionOfInterest
from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.file_controller import FileController, FrameSource
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.trajectory_detection import detect_sequence
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziSource
from apkit4d.tracking.linker import ParticleLinker


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
        update(row, "Opening", "")
        try:
            with closing(CziSource(path, channel=channel)) as source:
                info = source.info
                if (info.n_z, info.n_y, info.n_x) != shape:
                    raise ValueError(f"Volume dimensions differ from the reference {shape}.")
                if last >= info.n_t:
                    raise ValueError(f"Export ends at frame {last + 1}; recording has {info.n_t} frames.")
                data = detect_sequence(
                    source,
                    preproc,
                    detection,
                    roi,
                    progress_callback=lambda done, total, row=row: update(
                        row, f"Detecting {done}/{total}", ""
                    ),
                )
            tracks = None
            if tracking is not None:
                update(row, "Tracking", "")
                tracks = ParticleLinker(tracking).link(data.detections, dt_s=data.dt_s).tracks
            update(row, "Saving", "")
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
            update(row, f"Failed: {error}", "")
        else:
            completed += 1
            update(row, "Saved", str(result.params_path))
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

    Signals:
        recording_updated: Carries the row index, status, and optional result path.
    """

    recording_updated = Signal(int, str, str)

    def __init__(
        self,
        window: MainWindow,
        files: FileController,
        pipeline: PipelineModel,
        current_roi: Callable[[], RegionOfInterest | None],
        parent: QObject,
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._panel = window.multi_file_panel
        self._export = window.right_panel.batch_inspector
        self._files = files
        self._pipeline = pipeline
        self._current_roi = current_roi
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
        self._refresh()

    def _closed(self) -> None:
        self._reference = None
        self._refresh()

    def _open_failed(self, path: Path) -> None:
        if self._pending and path == self._pending[0]:
            self._clear_pending()

    def _clear_pending(self) -> None:
        self._pending = ()
        self._refresh()

    def _show_queue(self) -> None:
        """Rebuild the visible queue and mark every recording as ready."""
        self._panel.recordings.clear()
        for row, path in enumerate(self._recordings):
            self._panel.recordings.addItem(path.name)
            self._show_recording_status(row, "Ready", "")
        self._panel.status.clear()
        self._window.show_multi_file_panel()
        self._refresh()

    def _refresh(self) -> None:
        """Enable controls based on whether a reference is loaded and a batch can start."""
        idle = self._task is None and not self._pending
        self._window.open_files_action.setEnabled(idle)
        self._window.add_files_action.setEnabled(idle and self._reference is not None)
        self._panel.run.setEnabled(idle and self._reference is not None and bool(self._recordings))
        self._panel.tracking.setEnabled(idle)

    def _run(self) -> None:
        """Read settings on the GUI thread and submit the batch to the worker."""
        source = self._files.source
        if source is None or not self._panel.run.isEnabled():
            return
        folder = self._export.output_dir.text().strip()
        if not folder:
            self._panel.status.setText("Choose an existing output folder in Batch Export.")
            return

        output_dir = Path(folder).expanduser().resolve()
        if not output_dir.is_dir():
            self._panel.status.setText("Choose an existing output folder in Batch Export.")
            return
        first = self._export.first_frame.value() - 1
        last = self._export.last_frame.value() - 1
        if first > last:
            self._panel.status.setText("First frame cannot be greater than last frame in Batch Export.")
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
            self._current_roi(),
            preproc,
            detection,
            tracking,
            self.recording_updated.emit,
        )
        for row in range(len(self._recordings)):
            self._show_recording_status(row, "Queued", "")
        self._panel.status.setText("Processing recordings…")
        self._task = self._runner.run(job)
        self._refresh()

    def _show_recording_status(self, row: int, status: str, result: str) -> None:
        path = self._recordings[row]
        item = self._panel.recordings.item(row)
        item.setText(f"{path.name}  -  {status}" + (f"  -  {result}" if result else ""))
        item.setToolTip(f"{path}\n{result or status}")

    def _finished(self, task: int, completed: int) -> None:
        if task == self._task:
            self._task = None
            self._panel.status.setText(
                f"Saved results for {completed} of {len(self._recordings)} recordings."
            )
            self._refresh()

    def _failed(self, task: int, error: Exception) -> None:
        if task == self._task:
            self._task = None
            for row in range(len(self._recordings)):
                self._show_recording_status(row, "Failed", "")
            self._panel.status.setText(f"Could not start processing: {error}")
            self._refresh()
