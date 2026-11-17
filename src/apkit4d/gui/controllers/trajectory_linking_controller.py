"""Controller for asynchronous trajectory linking."""

from functools import partial
from typing import cast

import pandas as pd
from PySide6.QtCore import QObject, Signal

from apkit4d.core.models import TrackingConfig
from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.tracking.linker import ParticleLinker, TrackingResult


class TrajectoryLinkingController(QObject):
    """Run particle tracking without blocking the GUI."""

    result_ready = Signal(object)
    failed = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

        self._runner = TaskRunner(self)
        self._runner.succeeded.connect(self._on_success)
        self._runner.failed.connect(self._on_failure)

        self._task_id: int | None = None
        self.result: TrackingResult | None = None

    @property
    def is_running(self) -> bool:
        """Whether a linking task is currently running."""
        return self._task_id is not None

    def run(
        self,
        detections: pd.DataFrame,
        config: TrackingConfig,
        dt_s: float | None = None,
    ) -> bool:
        """Start linking detections in a background thread."""
        if self.is_running:
            return False

        self.result = None

        self._task_id = self._runner.run(
            partial(
                ParticleLinker(config).link,
                detections,
                dt_s=dt_s,
            )
        )
        return True

    def _on_success(self, task_id: int, result: object) -> None:
        if task_id != self._task_id:
            return

        self._task_id = None
        self.result = cast(TrackingResult, result)
        self.result_ready.emit(self.result)

    def _on_failure(self, task_id: int, error: object) -> None:
        if task_id != self._task_id:
            return

        self._task_id = None
        self.failed.emit(error)
