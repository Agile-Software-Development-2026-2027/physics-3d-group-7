"""
Controller of the opening of files.

It opens the file that the user chose in a background thread, so that the window stays responsive, and
keeps the recording that is open. The views are updated only when the file is really open, and a file
that cannot be opened is reported in the status bar without losing the one that was open before.
Saved results are opened together with their recording, so they are shown without running the analysis.
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Protocol

from numpy.typing import NDArray
from PySide6.QtCore import QObject, Signal

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziInfo, CziSource
from apkit4d.io.saved_results import SavedResults, read_saved_results
from apkit4d.io.session import PrecomputedFrameSource


class FrameSource(Protocol):
    """What the GUI needs from an open recording. `CziSource` provides it."""

    @property
    def info(self) -> CziInfo: ...

    def read(self, t: int) -> NDArray: ...

    def close(self) -> None: ...


type SourceOpener = Callable[[Path], FrameSource]


class FileController(QObject):
    """
    Opens files in the background and owns the recording that is open.

    Args:
        window: The view where the progress and the result of the opening are shown.
        open_source: Function that opens a file and returns its recording. It runs in a background
            thread, and it is `CziSource` unless a test needs a fake one.
        parent: Qt parent, so the controller lives as long as its owner.

    Signals:
        loaded: Emitted with the path and the recording once a file has been opened.
        closed: Emitted when a file is closed
        open_failed: Emitted with the path when the latest background open fails.
    """

    loaded = Signal(Path, object)
    closed = Signal()
    open_failed = Signal(Path)

    def __init__(
        self, window: MainWindow, open_source: SourceOpener = CziSource, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._window = window
        self._open_source = open_source
        self._source: FrameSource | None = None
        self._latest_task = 0  # the outcome of any other task is ignored
        self._latest_path = Path()

        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_opened)
        self._runner.failed.connect(self._on_failed)
        window.file_opened.connect(self.open_file)
        window.results_opened.connect(self.open_results)

    @property
    def source(self) -> FrameSource | None:
        """The recording that is open, None if no file has been opened yet."""
        return self._source

    def open_file(self, path: Path) -> None:
        """
        Start opening `path` in a background thread.

        Only the last file requested is shown: if another file is requested before this one is ready,
        this one is closed as soon as it is ready and nothing else happens.

        Args:
            path: File to open.
        """
        self.open_with(path, partial(self._open_source, path))

    def open_with(self, path: Path, opener: Callable[[], FrameSource]) -> None:
        """
        Start opening a recording via a custom zero-argument opener in a background thread.

        Args:
            path: Display path shown in the window title and status bar once opened.
            opener: Callable executed in the worker thread returning a `FrameSource`.
        """
        self._window.set_status(texts.STATUS_OPENING.format(name=path.name))
        self._latest_path = path
        self._latest_task = self._runner.run(opener)

    def open_results(self, params_path: Path) -> None:
        """
        Open the recording of saved results in a background thread, with the results on it.

        If the recording is neither where the results say nor next to them, the user is asked where it is.

        Args:
            params_path: The `<stem>_blobs_params.json` written when the results were saved.
        """
        try:
            results = read_saved_results(params_path)
        except (OSError, ValueError) as error:
            self._window.set_status(texts.STATUS_OPEN_FAILED.format(name=params_path.name, reason=error))
            return
        recording = results.recording or self._window.choose_recording(results.recording_name)
        if recording is None:
            reason = texts.RECORDING_NOT_FOUND.format(name=results.recording_name)
            self._window.set_status(texts.STATUS_OPEN_FAILED.format(name=params_path.name, reason=reason))
            return
        self.open_with(recording, partial(self._open_with_results, recording, results))

    def close(self) -> None:
        """Close the recording that is open, if any."""
        if self._source is not None:
            self._source.close()
            self._source = None
            self._window.set_current_file(None)
            self.closed.emit()

    def _on_opened(self, task_id: int, source: FrameSource) -> None:
        if task_id != self._latest_task:
            source.close()  # nobody wants this file anymore
            return
        self.close()  # the file that was open before
        self._source = source
        self._window.set_current_file(self._latest_path)
        self._window.set_status(texts.STATUS_OPENED.format(path=self._latest_path, frames=source.info.n_t))
        self.loaded.emit(self._latest_path, source)

    def _on_failed(self, task_id: int, error: Exception) -> None:
        if task_id != self._latest_task:
            return
        self.open_failed.emit(self._latest_path)
        reason = str(error) or type(error).__name__
        self._window.set_status(texts.STATUS_OPEN_FAILED.format(name=self._latest_path.name, reason=reason))

    def _open_with_results(self, path: Path, results: SavedResults) -> FrameSource:
        """Runs in the background thread: the recording comes back with the saved results attached."""
        session = results.load_session(path)  # first, so that a missing table leaves no recording open
        source = self._open_source(path)
        channel = getattr(source, "channel", 0)
        if channel != results.channel:
            source.close()
            raise ValueError(texts.RESULTS_OTHER_CHANNEL.format(saved=results.channel, opened=channel))
        return PrecomputedFrameSource(source, session, params_path=results.params_path.resolve())
