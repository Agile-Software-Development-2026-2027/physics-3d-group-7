"""
Runs functions in a background thread and delivers their outcome in the thread of the controller.

Reading a file or detecting blobs takes seconds, and doing it in the thread of the GUI would freeze the
window. A `TaskRunner` runs the function in a background thread and announces the outcome with a signal.
The controller receives the signal in its own thread, so the slot can safely touch the views.

Two precautions keep PySide from crashing the application, and both are needed:

- The threads are plain Python threads and not `QRunnable`s. Qt deletes a `QRunnable` by itself in the
  thread that ran it, and PySide cannot destroy the Python side of a Qt object from a thread other than
  the main one.
- The garbage collector of Python is paused while a task runs, and it is resumed by the GUI thread. The
  collector runs in the thread that allocates memory, and a task that raised an exception allocates a lot.
  A window and its controllers keep references to each other, so they are freed by the collector, and
  freeing them from a background thread destroys Qt widgets from the wrong thread.
"""

import gc
import os
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait
from contextlib import suppress
from itertools import count

import shiboken6
from PySide6.QtCore import QCoreApplication, QObject, Signal

_MIN_WORKERS = 2


class _CollectionPause(QObject):
    """
    Keeps the garbage collector paused while any task is running.

    It lives in the GUI thread, as a child of the application, so that the collector is always resumed
    there, even if the runner that started the task has been destroyed in the meantime.
    """

    _task_ended = Signal()

    def __init__(self) -> None:
        super().__init__(QCoreApplication.instance())
        self._lock = threading.Lock()
        self._running = 0
        self._was_enabled = True
        self._task_ended.connect(self.resume)  # queued, because it is emitted in a background thread

    def pause(self) -> None:
        """Pause the collector. Call it in the GUI thread, before starting the task."""
        with self._lock:
            if self._running == 0:
                self._was_enabled = gc.isenabled()
                gc.disable()
            self._running += 1

    def resume(self) -> None:
        """Count one task less, and resume the collector when there are none. GUI thread only."""
        with self._lock:
            self._running -= 1
            if self._running == 0 and self._was_enabled:
                gc.enable()

    def task_ended(self) -> None:
        """Tell the GUI thread that a task is over. Call it from the thread of the task."""
        self._task_ended.emit()


class _Shared:
    """What all the runners share: the threads, the pause of the collector and the tasks still running."""

    lock = threading.Lock()
    executor: ThreadPoolExecutor | None = None
    pause: _CollectionPause | None = None
    pending: set[Future[None]] = set()  # noqa: RUF012


def _get_executor() -> ThreadPoolExecutor:
    with _Shared.lock:
        if _Shared.executor is None:
            workers = max(_MIN_WORKERS, os.cpu_count() or _MIN_WORKERS)
            _Shared.executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="apkit4d-task")
        return _Shared.executor


def _get_pause() -> _CollectionPause:
    with _Shared.lock:
        if _Shared.pause is None or not shiboken6.isValid(_Shared.pause):  # a new application replaced it
            _Shared.pause = _CollectionPause()
        return _Shared.pause


def _forget(future: Future[None]) -> None:
    with _Shared.lock:
        _Shared.pending.discard(future)


def wait_for_background_tasks(timeout_s: float | None = None) -> bool:
    """
    Block until every task started by any `TaskRunner` has ended.

    It is meant for the moment when the application closes, and for the tests, which must not leave a
    task running after they end.

    Args:
        timeout_s: Seconds to wait, None to wait as long as needed.

    Returns:
        True if all the tasks have ended, False if the timeout expired first.
    """
    with _Shared.lock:
        futures = set(_Shared.pending)
    return not wait(futures, timeout=timeout_s).not_done


class TaskRunner(QObject):
    """
    Runs functions in background threads and reports how they ended.

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

    def run(self, function: Callable[[], object]) -> int:
        """
        Start `function` in a background thread. Call it from the GUI thread.

        Args:
            function: Function without arguments. Use `functools.partial` to bind them.

        Returns:
            The id of the task, to recognize its outcome among the ones of the other tasks.
        """
        pause = _get_pause()
        pause.pause()
        task_id = next(self._ids)
        try:
            future = _get_executor().submit(self._execute, task_id, function)
        except BaseException:
            pause.resume()
            raise
        with _Shared.lock:
            _Shared.pending.add(future)
        future.add_done_callback(_forget)
        return task_id

    def _execute(self, task_id: int, function: Callable[[], object]) -> None:
        try:
            try:
                result = function()
            except Exception as error:  # the error is handed to the controller, it must not die here
                self._announce(self.failed, task_id, error)
            else:
                self._announce(self.succeeded, task_id, result)
        finally:
            _get_pause().task_ended()

    @staticmethod
    def _announce(signal, task_id: int, value: object) -> None:
        with suppress(RuntimeError):  # the runner was destroyed while the task ran: nobody is waiting
            signal.emit(task_id, value)
