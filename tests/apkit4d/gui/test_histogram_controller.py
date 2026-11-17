from unittest.mock import MagicMock

import numpy as np
import pytest

from apkit4d.gui.controllers.histogram_controller import HistogramController
from apkit4d.gui.controllers.volume_controller import PreparedVolume, VolumeController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep
from apkit4d.gui.views.main_window import MainWindow
from apkit4d.gui.views.panels.preprocessing_section import PreprocessingSection
from apkit4d.gui.views.panels.right_panel import RightPanel
from apkit4d.gui.views.widgets.preprocessed_intensity_histogram import PreprocessedIntensityHistogram
from apkit4d.gui.views.widgets.roi_intensity_histogram import RoiIntensityHistogram


class FakeVolumeView:
    def __init__(self) -> None:
        self.grids: list[object] = []

    def show_volume(self, grid: object, reset_camera: bool = True, force_update: bool = False) -> None:
        self.grids.append((grid, reset_camera, force_update))


def test_histogram_controller_initialization(qtbot) -> None:
    histogram = RoiIntensityHistogram()
    preproc_histogram = PreprocessedIntensityHistogram()
    qtbot.addWidget(histogram)
    qtbot.addWidget(preproc_histogram)

    model = PipelineModel()
    model.update_step_params(PipelineStep.PREPROCESSING, lowest_intensity=123.0, highest_intensity=890.0)

    controller = HistogramController(
        histogram,
        volume_controller=None,
        pipeline_model=model,
        preproc_histogram=preproc_histogram,
    )
    assert controller.histogram is histogram
    assert histogram.lowest_intensity == pytest.approx(123.0)
    assert histogram.highest_intensity == pytest.approx(890.0)
    assert preproc_histogram.volume is None


def test_histogram_controller_volume_change(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    vol_ctrl = VolumeController(window, view)

    histogram = RoiIntensityHistogram()
    preproc_histogram = PreprocessedIntensityHistogram()
    qtbot.addWidget(histogram)
    qtbot.addWidget(preproc_histogram)
    model = PipelineModel()

    _ = HistogramController(
        histogram,
        vol_ctrl,
        model,
        preproc_histogram=preproc_histogram,
    )

    raw_vol = np.arange(1000, dtype=np.uint16).reshape((10, 10, 10))
    preproc_vol = np.linspace(0.0, 1.0, 1000, dtype=np.float32).reshape((10, 10, 10))

    vol_ctrl.roi_volume_changed.emit(raw_vol)
    assert histogram.volume is raw_vol

    prepared = PreparedVolume(
        is_image_normalized=True,
        frame=0,
        voxel=(1.0, 1.0, 1.0),
        roi_volume=raw_vol,
        image=preproc_vol,
        offset=(0, 0, 0),
    )
    vol_ctrl.volume_prepared.emit(prepared)
    assert preproc_histogram.volume is preproc_vol

    # Clearing the ROI volume (e.g. when loading a new file) clears both histograms
    vol_ctrl.roi_volume_changed.emit(None)
    assert histogram.volume is None
    assert preproc_histogram.volume is None


def test_histogram_controller_clears_preprocessed_histogram_on_volume_failed(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    vol_ctrl = VolumeController(window, view)

    histogram = RoiIntensityHistogram()
    preproc_histogram = PreprocessedIntensityHistogram()
    qtbot.addWidget(histogram)
    qtbot.addWidget(preproc_histogram)
    model = PipelineModel()

    _ = HistogramController(
        histogram,
        vol_ctrl,
        model,
        preproc_histogram=preproc_histogram,
    )

    raw_vol = np.ones((4, 4, 4), dtype=np.uint16)
    preproc_vol = np.full((4, 4, 4), 0.5, dtype=np.float32)
    vol_ctrl.volume_prepared.emit(
        PreparedVolume(
            is_image_normalized=True,
            frame=1,
            voxel=(1.0, 1.0, 1.0),
            roi_volume=raw_vol,
            image=preproc_vol,
            offset=(0, 0, 0),
        )
    )
    assert preproc_histogram.volume is preproc_vol

    vol_ctrl.failed.emit()
    assert preproc_histogram.volume is None


def test_histogram_controller_updates_preprocessed_on_preproc_done(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    vol_ctrl = VolumeController(window, view)
    vol_ctrl._usable = True
    vol_ctrl._current_roi_volume = np.arange(1, 65, dtype=np.uint16).reshape((4, 4, 4))

    histogram = RoiIntensityHistogram()
    preproc_histogram = PreprocessedIntensityHistogram()
    qtbot.addWidget(histogram)
    qtbot.addWidget(preproc_histogram)
    model = PipelineModel()

    _ = HistogramController(
        histogram,
        vol_ctrl,
        model,
        preproc_histogram=preproc_histogram,
    )

    frame_0_out = np.full((4, 4, 4), 0.25, dtype=np.float32)
    vol_ctrl._on_preproc_done(1, frame_0_out)
    assert preproc_histogram.volume is frame_0_out

    # Subsequent frame during playback updates the preprocessed histogram again
    frame_1_out = np.full((4, 4, 4), 0.75, dtype=np.float32)
    vol_ctrl._current_frame = 1
    vol_ctrl._on_preproc_done(2, frame_1_out)
    assert preproc_histogram.volume is frame_1_out


def test_histogram_controller_param_change(qtbot) -> None:
    histogram = RoiIntensityHistogram()
    qtbot.addWidget(histogram)
    model = PipelineModel()

    _ = HistogramController(histogram, volume_controller=None, pipeline_model=model)

    model.update_step_params(PipelineStep.PREPROCESSING, lowest_intensity=250.0, highest_intensity=750.0)

    assert histogram.lowest_intensity == pytest.approx(250.0)
    assert histogram.highest_intensity == pytest.approx(750.0)


def test_histogram_controller_drag_with_normalization_enabled(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    vol_ctrl = VolumeController(window, view)
    vol = np.arange(1, 1001, dtype=np.uint16).reshape((10, 10, 10))
    vol_ctrl._usable = True
    vol_ctrl._current_roi_volume = vol

    right_panel = RightPanel()
    qtbot.addWidget(right_panel)
    preproc_section = right_panel.get_section(PipelineStep.PREPROCESSING)
    assert isinstance(preproc_section, PreprocessingSection)

    model = PipelineModel()
    model.update_step_params(PipelineStep.PREPROCESSING, normalization_enabled=True)
    vol_ctrl._preproc_params = model.get_preproc_params()

    right_panel.step_param_changed.connect(
        lambda step_name, param, val: model.update_step_params(PipelineStep(step_name), **{param: val})
    )
    model.step_params_changed.connect(
        lambda s: (
            vol_ctrl.apply_preproc_params(model.get_preproc_params())
            if s == PipelineStep.PREPROCESSING
            else None
        )
    )

    histogram = RoiIntensityHistogram()
    qtbot.addWidget(histogram)
    _ = HistogramController(histogram, vol_ctrl, model, preproc_section=preproc_section)

    vol_ctrl._start_preprocessing = MagicMock()

    histogram.lowest_line.setValue(45.0)  # drag lowest line
    histogram.lowest_line.sigDragged.emit(histogram.lowest_line)

    assert preproc_section.lowest_instensity.value() == pytest.approx(45.0)
    assert vol_ctrl._start_preprocessing.call_count == 1

    histogram.highest_line.setValue(850.0)  # drag highest line
    histogram.highest_line.sigDragged.emit(histogram.highest_line)

    assert preproc_section.highest_intensity.value() == pytest.approx(850.0)
    assert vol_ctrl._start_preprocessing.call_count == 2


def test_histogram_controller_drag_with_normalization_disabled(qtbot) -> None:
    window = MainWindow()
    qtbot.addWidget(window)
    view = FakeVolumeView()
    vol_ctrl = VolumeController(window, view)
    vol = np.arange(1, 1001, dtype=np.uint16).reshape((10, 10, 10))
    vol_ctrl._usable = True
    vol_ctrl._current_roi_volume = vol

    right_panel = RightPanel()
    qtbot.addWidget(right_panel)
    preproc_section = right_panel.get_section(PipelineStep.PREPROCESSING)
    assert isinstance(preproc_section, PreprocessingSection)

    model = PipelineModel()
    model.update_step_params(PipelineStep.PREPROCESSING, normalization_enabled=False)
    vol_ctrl.apply_preproc_params(model.get_preproc_params())

    right_panel.step_param_changed.connect(
        lambda step_name, param, val: model.update_step_params(PipelineStep(step_name), **{param: val})
    )
    model.step_params_changed.connect(
        lambda s: (
            vol_ctrl.apply_preproc_params(model.get_preproc_params())
            if s == PipelineStep.PREPROCESSING
            else None
        )
    )

    histogram = RoiIntensityHistogram()
    qtbot.addWidget(histogram)
    _ = HistogramController(histogram, vol_ctrl, model, preproc_section=preproc_section)

    vol_ctrl._start_preprocessing = MagicMock()

    # Drag lowest line with normalization disabled
    histogram.lowest_line.setValue(80.0)
    histogram.lowest_line.sigDragged.emit(histogram.lowest_line)

    # PreprocessingSection value was updated
    assert preproc_section.lowest_instensity.value() == pytest.approx(80.0)
    # But preprocessing was NOT run because normalization_enabled is False
    assert vol_ctrl._start_preprocessing.call_count == 0
