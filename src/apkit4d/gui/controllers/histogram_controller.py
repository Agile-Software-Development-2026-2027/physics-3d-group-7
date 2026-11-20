"""
Controller coordinating the intensity histogram with volume data and preprocessing settings.
"""

from functools import partial
from typing import cast

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCore import QObject

from apkit4d.gui.controllers.task_runner import TaskRunner
from apkit4d.gui.controllers.volume_controller import PreparedVolume, VolumeController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.histograms.preprocessed_intensity_histogram import (
    PreprocessedIntensityHistogram,
    compute_preprocessed_histogram,
)
from apkit4d.gui.views.histograms.roi_intensity_histogram import (
    RoiIntensityHistogram,
    compute_roi_histogram_stats,
)
from apkit4d.gui.views.stages.preprocessing_section import PreprocessingSection


class HistogramController(QObject):
    """
    Connects the ROI intensity histogram with VolumeController and PreprocessingSection.
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

        # roi histogram background runner
        self._roi_runner = TaskRunner(self)
        self._roi_runner.succeeded.connect(self._on_roi_hist_done)
        self._roi_runner.failed.connect(self._on_roi_hist_failed)
        self._roi_busy = False
        self._roi_pending = False
        self._roi_generation = 0
        self._roi_in_flight_meta: tuple[int, bool] = (0, False)

        self._histogram.set_async_mode(True)
        self._histogram.recompute_requested.connect(self._schedule_roi_recompute)

        # preprocessed histogram background runner
        self._preproc_runner = TaskRunner(self)
        self._preproc_runner.succeeded.connect(self._on_preproc_hist_done)
        self._preproc_runner.failed.connect(self._on_preproc_hist_failed)
        self._preproc_busy = False
        self._preproc_pending = False
        self._preproc_generation = 0
        self._preproc_in_flight_meta: tuple[int, bool] = (0, False)

        if self._preproc_histogram is not None:
            self._preproc_histogram.set_async_mode(True)
            self._preproc_histogram.recompute_requested.connect(self._schedule_preproc_recompute)

        initial_params = pipeline_model.get_preproc_params()
        self._histogram.set_intensity_bounds(
            initial_params.lowest_intensity, initial_params.highest_intensity
        )
        self._histogram.set_normalization_enabled(initial_params.normalization_enabled)

        # connect VolumeController volume events
        if self._volume_controller is not None:
            self._volume_controller.roi_volume_changed.connect(self._on_roi_volume_changed)
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

    def _start_roi_task(self, volume: NDArray, reset_range: bool) -> None:
        self._roi_busy = True
        self._roi_in_flight_meta = (self._roi_generation, reset_range)
        self._roi_runner.run(
            partial(
                compute_roi_histogram_stats,
                volume,
                self._histogram.lowest_intensity,
                self._histogram.highest_intensity,
                self._histogram.NUM_BINS,
            )
        )

    def _schedule_roi_recompute(self, reset_range: bool) -> None:
        self._roi_generation += 1
        vol = self._histogram.volume

        if vol is None or vol.size == 0:
            self._roi_pending = False
            bins, counts, top, frac_sat = compute_roi_histogram_stats(
                None,
                lowest_intensity=self._histogram.lowest_intensity,
                highest_intensity=self._histogram.highest_intensity,
                num_bins=self._histogram.NUM_BINS,
            )
            self._histogram.apply_computed_data(bins, counts, top, frac_sat, reset_range=reset_range)
            return

        if self._roi_busy:
            self._roi_pending = True
            return

        self._start_roi_task(vol, reset_range)

    def _on_roi_hist_done(self, _task_id: int, result: tuple[NDArray, NDArray, float, float]) -> None:
        self._roi_busy = False
        gen, reset_range = self._roi_in_flight_meta

        if gen == self._roi_generation and self._histogram.is_expanded:
            bins, counts, top, frac_sat = result
            self._histogram.apply_computed_data(bins, counts, top, frac_sat, reset_range=reset_range)

        if self._roi_pending:
            self._roi_pending = False
            if self._histogram.is_expanded:
                self._schedule_roi_recompute(self._histogram.pending_reset_range)

    def _on_roi_hist_failed(self, _task_id: int, _error: Exception) -> None:
        self._roi_busy = False
        if self._roi_pending:
            self._roi_pending = False
            if self._histogram.is_expanded:
                self._schedule_roi_recompute(self._histogram.pending_reset_range)

    def _start_preproc_task(self, volume: NDArray, reset_range: bool) -> None:
        if self._preproc_histogram is None:
            return
        self._preproc_busy = True
        self._preproc_in_flight_meta = (self._preproc_generation, reset_range)
        self._preproc_runner.run(
            partial(compute_preprocessed_histogram, volume, self._preproc_histogram.NUM_BINS)
        )

    def _schedule_preproc_recompute(self, reset_range: bool) -> None:
        if self._preproc_histogram is None:
            return

        self._preproc_generation += 1
        vol = self._preproc_histogram.volume

        if vol is None or vol.size == 0:
            self._preproc_pending = False
            bins, counts = compute_preprocessed_histogram(None, num_bins=self._preproc_histogram.NUM_BINS)
            self._preproc_histogram.apply_computed_data(bins, counts, reset_range=reset_range)
            return

        if self._preproc_busy:
            self._preproc_pending = True
            return

        self._start_preproc_task(vol, reset_range)

    def _on_preproc_hist_done(self, _task_id: int, result: tuple[NDArray, NDArray]) -> None:
        self._preproc_busy = False
        gen, reset_range = self._preproc_in_flight_meta

        if (
            self._preproc_histogram is not None
            and gen == self._preproc_generation
            and self._preproc_histogram.is_expanded
        ):
            bins, counts = result
            self._preproc_histogram.apply_computed_data(bins, counts, reset_range=reset_range)

        if self._preproc_pending:
            self._preproc_pending = False
            if self._preproc_histogram is not None and self._preproc_histogram.is_expanded:
                self._schedule_preproc_recompute(self._preproc_histogram.pending_reset_range)

    def _on_preproc_hist_failed(self, _task_id: int, _error: Exception) -> None:
        self._preproc_busy = False
        if self._preproc_pending:
            self._preproc_pending = False
            if self._preproc_histogram is not None and self._preproc_histogram.is_expanded:
                self._schedule_preproc_recompute(self._preproc_histogram.pending_reset_range)

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

    def _on_step_params_changed(self, step: PipelineStep) -> None:
        """Handle pipeline step parameter updates from PipelineModel."""
        if step == PipelineStep.PREPROCESSING:
            params = self._pipeline_model.get_preproc_params()
            if (
                self._histogram.lowest_intensity != params.lowest_intensity
                or self._histogram.highest_intensity != params.highest_intensity
            ):
                self._histogram.set_intensity_bounds(params.lowest_intensity, params.highest_intensity)
            self._histogram.set_normalization_enabled(params.normalization_enabled)

    def _on_lowest_intensity_dragged(self, value: float) -> None:
        """Update PreprocessingSection (with signals blocked) and PipelineModel directly."""
        if self._preproc_section is not None:
            self._preproc_section.set_lowest_intensity(value)
        self._pipeline_model.update_step_params(PipelineStep.PREPROCESSING, lowest_intensity=value)

    def _on_highest_intensity_dragged(self, value: float) -> None:
        """Update PreprocessingSection (with signals blocked) and PipelineModel directly."""
        if self._preproc_section is not None:
            self._preproc_section.set_highest_intensity(value)
        self._pipeline_model.update_step_params(PipelineStep.PREPROCESSING, highest_intensity=value)
