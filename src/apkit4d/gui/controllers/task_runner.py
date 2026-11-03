"""
Runs functions in a background thread and delivers their outcome in the thread of the controller.

Reading a file or detecting blobs takes seconds, and doing it in the thread of the GUI would freeze the
window. A `TaskRunner` runs the function in the Qt thread pool and announces the outcome with a signal.
The controller receives the signal in its own thread, so the slot can safely touch the views.
"""

from collections.abc import Callable
from itertools import count
from typing import override

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Job(QRunnable):
    """One function to run in the thread pool. It reports its outcome to the runner that created it."""

    def __init__(self, task_id: int, function: Callable[[], object], runner: TaskRunner) -> None:
        super().__init__()
        self._task_id = task_id
        self._function = function
        self._runner = runner

    @override
    def run(self) -> None:
        try:
            result = self._function()
        except Exception as error:  # the error is handed to the controller, it must not die in the thread
            self._runner.failed.emit(self._task_id, error)
        else:
            self._runner.succeeded.emit(self._task_id, result)


class TaskRunner(QObject):
    """
    Runs functions in the Qt thread pool and reports how they ended.

    Every function gets an id, so a controller that starts many tasks can recognize which one an outcome
    belongs to and ignore the outcome of tasks that are not wanted anymore.

    Args:
        parent: Qt parent, so the runner lives as long as its owner.

    Signals:
        succeeded: Emitted with the id of the task and the value it returned.
        failed: Emitted with the id of the task and the exception it raised.
    """

    succeeded = Signal(int, object)
    failed = Signal(int, object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ids = count(1)
        self._pool = QThreadPool.globalInstance()

    def run(self, function: Callable[[], object]) -> int:
        """
        Start `function` in a background thread.

        Args:
            function: Function without arguments. Use `functools.partial` to bind them.

        Returns:
            The id of the task, to recognize its outcome among the ones of the other tasks.
        """
        task_id = next(self._ids)
        self._pool.start(_Job(task_id, function, self))
        return task_id
