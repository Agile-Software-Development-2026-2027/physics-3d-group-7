"""
Read back the results saved by the app, so they can be shown again on their recording.

An export writes `<stem>_blobs_params.json` next to its tables: the json says which recording was
analysed, with which parameters, and which tables were saved (`table` for the blobs, `tracks_table`
for the tracks). Exports made before these keys existed, also by the old ApKit4D, can still be read:
their tables are looked for next to the json with the usual `<stem>_blobs` and `<stem>_tracks` names.
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from typing import Any, Final

import pandas as pd

from apkit4d.core.models import DetectionConfig, PreprocessingConfig, TrackingConfig
from apkit4d.io.session import PrecomputedSession
from apkit4d.io.table import find_table, read_table
from apkit4d.tracking.linker import TrackingResult

__all__ = ["PARAMS_SUFFIX", "SavedResults", "read_saved_results"]

logger = logging.getLogger(__name__)

PARAMS_SUFFIX: Final[str] = "_blobs_params.json"


@dataclass(frozen=True)
class SavedResults:
    """
    The json of saved results and the recording they belong to. The tables are read by `load_session`.

    Attributes:
        params_path: The `<stem>_blobs_params.json` file.
        metadata: What the json contains.
        recording: The recording the results were computed on, None if it is neither where the json
            says nor next to the results.
    """

    params_path: Path
    metadata: dict[str, Any]
    recording: Path | None

    @property
    def recording_name(self) -> str:
        """File name of the recording, also when the json was written on another operating system."""
        # PureWindowsPath splits on both / and \, while Path on Linux would not split a Windows path
        return PureWindowsPath(self.metadata["czi"]).name

    @property
    def channel(self) -> int:
        """Channel of the recording the results were computed on."""
        return int(self.metadata.get("channel", 0))

    def load_session(self) -> PrecomputedSession:
        """
        Read the saved tables and parameters, ready to be shown on the recording.

        Parameters that cannot be read, like the preprocessing of the old ApKit4D that used other
        names, are left out: the blobs and the tracks are shown anyway.

        Raises:
            FileNotFoundError: If a table that was saved is missing.
        """
        blobs_path = self._table_path("table", "blobs")
        if blobs_path is not None:
            blobs = read_table(blobs_path)
        elif int(self.metadata.get("n_blobs", 0)) > 0:
            raise FileNotFoundError(f"The blobs table of {self.params_path.name} is missing")
        else:
            blobs = pd.DataFrame(columns=["frame", "z_um", "y_um", "x_um"])  # nothing was detected

        tracking = None
        tracks_path = self._table_path("tracks_table", "tracks")
        if tracks_path is not None:
            tracks = read_table(tracks_path)
            if "track_id" not in tracks and "particle" in tracks:  # tracks of the old ApKit4D
                tracks = tracks.rename(columns={"particle": "track_id"})
            tracking = TrackingResult(tracks=tracks, metadata={})

        return PrecomputedSession(
            blobs=blobs,
            tracking=tracking,
            preproc_params=self._params("preproc", PreprocessingConfig.model_validate),
            blob_params=self._params("blob", DetectionConfig.model_validate),
            tracking_config=self._params("tracking", TrackingConfig.model_validate),
        )

    def _table_path(self, key: str, suffix: str) -> Path | None:
        """Where the table saved under `key` is, None if no such table was saved."""
        folder = self.params_path.parent
        if key in self.metadata:
            name = self.metadata[key]
            if not name:
                return None  # the export had nothing to save
            path = folder / name
            if not path.is_file():
                raise FileNotFoundError(f"{name} not found next to {self.params_path.name}")
            return path
        # older exports do not name their tables, they only follow the naming convention
        if not self.params_path.name.endswith(PARAMS_SUFFIX):
            return None
        return find_table(folder, self.params_path.name.removesuffix(PARAMS_SUFFIX), suffix)

    def _params[T](self, key: str, build: Callable[[dict[str, Any]], T]) -> T | None:
        """The parameters saved under `key`, None if they are missing or cannot be read."""
        saved = self.metadata.get(key)
        if not isinstance(saved, dict):
            return None
        try:
            return build(saved)
        except (TypeError, ValueError) as error:
            logger.warning("Ignoring the %s parameters of %s: %s", key, self.params_path.name, error)
            return None


def read_saved_results(params_path: Path) -> SavedResults:
    """
    Read the json of saved results and look for their recording.

    The recording is looked for where the json says, then next to the json and in the folder above it,
    since results are often saved in a subfolder (like `out`) of the recordings.

    Args:
        params_path: The `<stem>_blobs_params.json` written by an export.

    Raises:
        OSError: If the file cannot be read.
        ValueError: If the file is not the json of saved results.
    """
    try:
        metadata = json.loads(params_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ValueError(f"{params_path.name} is not a valid json file") from error
    if not isinstance(metadata, dict) or not isinstance(metadata.get("czi"), str):
        raise ValueError(f"{params_path.name} does not describe saved results")
    return SavedResults(params_path, metadata, _find_recording(params_path, metadata["czi"]))


def _find_recording(params_path: Path, written: str) -> Path | None:
    name = PureWindowsPath(written).name
    folder = params_path.parent
    for candidate in (Path(written), folder / written, folder / name, folder.parent / name):
        if candidate.is_file():
            return candidate.resolve()
    return None
