"""
Controller of the opening of files.

It opens the file that the user chose in a background thread, so that the window stays responsive, and
keeps the recording that is open. The views are updated only when the file is really open, and a file
that cannot be opened is reported in the status bar without losing the one that was open before.
"""

from collections.abc import Callable
from functools import partial
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QObject, Signal

from apkit4d.gui.constants import texts
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.io.czi import CziInfo, CziSource


class FrameSource(Protocol):
    """What the GUI needs from an open recording. `CziSource` provides it."""

    @property
    def info(self) -> CziInfo: ...

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
    """

    loaded = Signal(Path, object)

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
        self._window.set_status(texts.STATUS_OPENING.format(name=path.name))
        self._latest_path = path
        self._latest_task = self._runner.run(partial(self._open_source, path))

    def close(self) -> None:
        """Close the recording that is open, if any."""
        if self._source is not None:
            self._source.close()
            self._source = None

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
        reason = str(error) or type(error).__name__
        self._window.set_status(texts.STATUS_OPEN_FAILED.format(name=self._latest_path.name, reason=reason))
