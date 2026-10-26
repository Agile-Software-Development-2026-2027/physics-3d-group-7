from dataclasses import dataclass
from pathlib import Path

import czifile
import numpy as np


@dataclass
class CziInfo:
    """
    Stores metadata of a CZI microscopy acquisition.

    Attributes:
        path: Path to the CZI file.
        n_t: Number of time points.
        n_z: Number of Z slices.
        n_y: Image height in pixels.
        n_x: Image width in pixels.
        n_c: Number of channels.
        dtype: Pixel data type.
        px_size_x: Pixel size along X in µm.
        px_size_y: Pixel size along Y in µm.
        px_size_z: Voxel spacing along Z in µm.
        dt_s: Time interval in seconds, if available.
        dt_source: Source of the time interval.
    """

    path: str  # CZI file path
    n_t: int  # Time points
    n_z: int  # Z slices
    n_y: int  # Image height
    n_x: int  # Image width
    n_c: int  # Channels
    dtype: str  # Pixel data type

    px_size_x: float  # X pixel size (µm)
    px_size_y: float  # Y pixel size (µm)
    px_size_z: float  # Z pixel size (µm)

    dt_s: float | None  # Time step (s)
    dt_source: str  # Time step source (so far always "unknown")

    @property
    def voxel(self) -> tuple[float, float, float]:
        """
        Returns the physical voxel size.

        Returns:
            Voxel size (Z, Y, X) in micrometers.
        """
        return self.px_size_z, self.px_size_y, self.px_size_x


class CziSource:
    """
    Provide access to microscopy data from a CZI file.
    """

    def __init__(self, path: str | Path, channel: int = 0):
        """
        Opens a CZI file and loads its metadata.

        Args:
            path: Path to the CZI file.
            channel: Channel index to read. Defaults to 0.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If required axes are missing or the channel is invalid.
        """
        self.path = Path(path)
        self.channel = channel

        if not self.path.is_file():
            raise FileNotFoundError(f"CZI file not found: {self.path}")

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
                raise ValueError(f"CZI file is missing required axes: {sorted(missing_axes)}")

            n_channels = sizes.get("C", 1)

            # Check that the selected channel exists.
            if self.channel < 0 or self.channel >= n_channels:
                raise ValueError(f"Invalid channel {self.channel}. Available channels: 0-{n_channels - 1}")

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
                px_size_x=scales.get("X", default_scale) * meters_to_um,
                px_size_y=scales.get("Y", default_scale) * meters_to_um,
                px_size_z=scales.get("Z", default_scale) * meters_to_um,
                dt_s=None,
                dt_source="unknown",
            )

        except Exception:
            self.close()
            raise

    def read(self, t: int = 0) -> np.ndarray:
        """
        Read a single 3D volume at the specified time point.

        Args:
            t: Time point index. Defaults to 0.

        Returns:
            NumPy array containing the selected 3D volume.

        Raises:
            IndexError: If the time point is out of range.
        """
        # Check that the requested time point exists.
        if t < 0 or t >= self.info.n_t:
            raise IndexError(f"Invalid time point {t}. Available time points: 0-{self.info.n_t - 1}")

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
