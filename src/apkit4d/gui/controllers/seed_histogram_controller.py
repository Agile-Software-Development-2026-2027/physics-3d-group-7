import numpy as np
from PySide6.QtCore import QObject

from apkit4d.gui.controllers.blob_detection_controller import BlobDetectionController
from apkit4d.gui.views.widgets.blob_detection_inspector import BlobDetectionInspector
from apkit4d.gui.views.widgets.seed_response_histogram import SeedResponseHistogram


class SeedHistogramController(QObject):
    """
    Keeps the line of the histogram and the LoG threshold of the inspector on the same value.
    It also gives the response of the candidates of every detection to the histogram.

    Create it after the `BlobDetectionController`, because that is what sets the starting
    threshold of the inspector.

    Args:
        histogram: The histogram of the LoG response.
        inspector: The blob detection inspector.
        blob_controller: The controller that announces the response of the candidates.
        parent: Qt parent, so the controller lives as long as its owner.
    """

    def __init__(
        self,
        histogram: SeedResponseHistogram,
        inspector: BlobDetectionInspector,
        blob_controller: BlobDetectionController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._histogram = histogram
        self._inspector = inspector

        histogram.set_threshold(inspector.lo_g_threshold)

        # histogram -> inspector
        histogram.threshold_changed_by_user.connect(self._on_threshold_released)
        # inspector -> histogram
        inspector.lo_g_changed.connect(histogram.set_threshold)
        # blob controller -> histogram
        blob_controller.seeds_response_changed.connect(self._on_seeds_response)

    @property
    def histogram(self) -> SeedResponseHistogram:
        """The controlled histogram view."""
        return self._histogram

    def _on_threshold_released(self, value: float) -> None:
        # this change trigger the lo_g_changed signal emission and it'll
        # produce a blob detection if update_on_change is enabled
        self._inspector.lo_g_threshold = value
        self._histogram.set_threshold(self._inspector.lo_g_threshold)

    def _on_seeds_response(self, values: object) -> None:
        if values is None or isinstance(values, np.ndarray):
            self._histogram.set_seeds_response(values)
        else:
            raise TypeError(f"values should be of type {np.ndarray} | {None}, got {type(values).__name__}")
