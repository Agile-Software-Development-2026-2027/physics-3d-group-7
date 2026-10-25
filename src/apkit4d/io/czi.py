from dataclasses import dataclass
from pathlib import Path

import czifile
import numpy as np


@dataclass
class CziInfo:
    """
    Metadata describing a CZI microscopy acquisition.
    """

    path: str
    n_t: int
    n_z: int
    n_y: int
    n_x: int
    n_c: int
    dtype: str

    px_x: float  # Voxel size in µm
    px_y: float
    px_z: float

    dt_s: float | None  
    dt_source: str

    @property
    def voxel(self) -> tuple[float, float, float]:
        """
        Return voxel size in (Z, Y, X) order, in µm.
        """
        return self.px_z, self.px_y, self.px_x

class CziSource:
    """
    Read microscopy data from a CZI file.
    """

    def __init__(self, path: str | Path, channel: int = 0):
        self.path = Path(path)
        self.channel = channel

        if not self.path.is_file():
            raise FileNotFoundError(
                f"CZI file not found: {self.path}"
            )

        self._czi = czifile.CziFile(self.path)

        try:
            scene = self._czi.scenes[0]
            sizes = scene.sizes

            # Store axis dimensions for selecting time points and channels.
            self._dims = sizes

            # Valid 3D volume must contain Z, Y and X axes.
            required_axes = {"Z", "Y", "X"}
            missing_axes = required_axes - sizes.keys()

            if missing_axes:
                raise ValueError(
                    f"CZI file is missing required axes: {sorted(missing_axes)}"
                )

            n_channels = sizes.get("C", 1)

            # Check that the selected channel exists.
            if self.channel < 0 or self.channel >= n_channels:
                raise ValueError(
                    f"Invalid channel {self.channel}. "
                    f"Available channels: 0-{n_channels - 1}"
                )

            # CZI spatial calibration is stored in meters.
            # Convert it to micrometers, as expected by CziInfo.
            meters_to_um = 1e6

            # Use 1 µm as a fallback when spatial calibration is missing.
            default_scale = 1e-6

            scales = scene.coord_scales

            self.info = CziInfo(
                path=str(self.path),
                n_t=sizes.get("T", 1),
                n_z=sizes["Z"],
                n_y=sizes["Y"],
                n_x=sizes["X"],
                n_c=n_channels,
                dtype=str(scene.dtype),
                px_x=scales.get("X", default_scale) * meters_to_um,
                px_y=scales.get("Y", default_scale) * meters_to_um,
                px_z=scales.get("Z", default_scale) * meters_to_um,
                dt_s=None,
                dt_source="unknown",
            )

        except Exception:
            self.close()
            raise

    def read(self, t: int = 0) -> np.ndarray:
        """
        Read a single 3D volume at the specified time point.
        """
        # Check that the requested time point exists.
        if t < 0 or t >= self.info.n_t:
            raise IndexError(
                f"Invalid time point {t}. "
                f"Available time points: 0-{self.info.n_t - 1}"
            )

        # Select only axes that are present in the CZI file.
        if "T" in self._dims and "C" in self._dims:
            return self._czi.asarray(T=t, C=self.channel)

        if "T" in self._dims:
            return self._czi.asarray(T=t)

        if "C" in self._dims:
            return self._czi.asarray(C=self.channel)

        return self._czi.asarray()

    def close(self) -> None:
        """
        Close the CZI file and release its resources.
        """
        self._czi.close()