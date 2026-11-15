"""
Controller coordinating the intensity histogram with volume data and preprocessing settings.
"""

from typing import cast

import numpy as np
from PySide6.QtCore import QObject

from apkit4d.gui.controllers.volume_controller import PreparedVolume, VolumeController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.panels.preprocessing_section import PreprocessingSection
from apkit4d.gui.views.widgets.preprocessed_intensity_histogram import PreprocessedIntensityHistogram
from apkit4d.gui.views.widgets.roi_intensity_histogram import RoiIntensityHistogram
from apkit4d.preprocessing import PreprocParams

__all__ = ["HistogramController"]


class HistogramController(QObject):
    """
    Connects the ROI intensity histogram with VolumeController and PreprocessingSection.

    Keeps the histogram syncrhonzied with the current roi volume, with the PreprocParams
    in the GUI. Changing the window bounds when normalization is off doesn't cause
    preprocessing to run again.

    Args:
        histogram: The interactive ROI histogram widget.
        volume_controller: The 3D view volume controller, or None.
        pipeline_model: Pipeline state model holding step parameters.
        preproc_section: Optional PreprocessingSection widget in RightPanel.
        parent: Optional Qt parent.
    """

    def __init__(
        self,
        histogram: RoiIntensityHistogram,
        volume_controller: VolumeController | None,
        pipeline_model: PipelineModel,
        preproc_histogram: PreprocessedIntensityHistogram | None = None,
        preproc_section: PreprocessingSection | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._histogram = histogram
        self._volume_controller = volume_controller
        self._pipeline_model = pipeline_model
        self._preproc_section = preproc_section
        self._preproc_histogram = preproc_histogram

        initial_params = pipeline_model.get_preproc_params()
        self._histogram.set_intensity_bounds(
            initial_params.lowest_intensity, initial_params.highest_intensity
        )
        self._histogram.set_normalization_enabled(initial_params.normalization_enabled)

        # connect VolumeController volume and params events
        if self._volume_controller is not None:
            self._volume_controller.roi_volume_changed.connect(self._on_roi_volume_changed)
            self._volume_controller.preproc_params_changed.connect(self._on_volume_preproc_params_changed)
            self._volume_controller.volume_prepared.connect(self._on_volume_prepared)
            self._volume_controller.failed.connect(self._on_volume_failed)
            if self._volume_controller.current_roi_volume is not None:
                self._histogram.set_volume(self._volume_controller.current_roi_volume)

        # step_params_changed -> intensity_changed
        self._pipeline_model.step_params_changed.connect(self._on_step_params_changed)

        # intensity_changed -> step_params_changed
        self._histogram.lowest_intensity_changed.connect(self._on_lowest_intensity_dragged)
        self._histogram.highest_intensity_changed.connect(self._on_highest_intensity_dragged)

    @property
    def histogram(self) -> RoiIntensityHistogram:
        """The controlled histogram view."""
        return self._histogram

    def _on_roi_volume_changed(self, volume: object) -> None:
        """Handle volume change from VolumeController"""

        if volume is None or isinstance(volume, np.ndarray):
            self._histogram.set_volume(cast(np.ndarray | None, volume))
            if volume is None and self._preproc_histogram is not None:
                self._preproc_histogram.set_volume(None)

    def _on_volume_prepared(self, prepared: object) -> None:
        if self._preproc_histogram is None:
            return
        if isinstance(prepared, PreparedVolume):
            self._preproc_histogram.set_volume(prepared.image)

    def _on_volume_failed(self) -> None:
        if self._preproc_histogram is not None:
            self._preproc_histogram.set_volume(None)

    def _on_volume_preproc_params_changed(self, params: object) -> None:
        """Handle parameter updates directly from VolumeController."""

        if isinstance(params, PreprocParams):
            self._histogram.set_intensity_bounds(params.lowest_intensity, params.highest_intensity)
            self._histogram.set_normalization_enabled(params.normalization_enabled)

    def _on_step_params_changed(self, step: PipelineStep) -> None:
        """Handle pipeline step parameter updates from PipelineModel."""

        if step == PipelineStep.PREPROCESSING:
            params = self._pipeline_model.get_preproc_params()
            self._histogram.set_intensity_bounds(params.lowest_intensity, params.highest_intensity)
            self._histogram.set_normalization_enabled(params.normalization_enabled)

    def _on_lowest_intensity_dragged(self, value: float) -> None:
        """Update PreprocessingSection and model when lowest_intensity line is dragged."""

        if self._preproc_section is not None:
            self._preproc_section.set_lowest_intensity(value)
        else:
            self._pipeline_model.update_step_params(PipelineStep.PREPROCESSING, lowest_intensity=value)

    def _on_highest_intensity_dragged(self, value: float) -> None:
        """Update PreprocessingSection and model when highest_intensity line is dragged."""

        if self._preproc_section is not None:
            self._preproc_section.set_highest_intensity(value)
        else:
            self._pipeline_model.update_step_params(PipelineStep.PREPROCESSING, highest_intensity=value)
