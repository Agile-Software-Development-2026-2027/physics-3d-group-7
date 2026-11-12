"""
Controller that bridges preprocessing parameter changes in the model
to the live 3D preview in the VolumeController.
"""

from PySide6.QtCore import QObject

from apkit4d.gui.controllers.volume_controller import VolumeController
from apkit4d.gui.models.pipeline_model import PipelineModel, PipelineStep


class PreprocessingController(QObject):
    """
    Listens for preprocessing parameter changes on the PipelineModel
    and applies them to the VolumeController for live preview.

    Args:
        model: The pipeline model that holds PreprocParams.
        volume_controller: The controller that owns the 3D view.
        parent: Qt parent object.
    """

    def __init__(
        self,
        model: PipelineModel,
        volume_controller: VolumeController,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._model = model
        self._volume_controller = volume_controller

        self._model.step_params_changed.connect(self._on_step_params_changed)

    def _on_step_params_changed(self, step: PipelineStep) -> None:
        if step == PipelineStep.PREPROCESSING:
            self._volume_controller.apply_preproc_params(self._model.get_preproc_params())
