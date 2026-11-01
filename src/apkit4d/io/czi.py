import re
import threading
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import czifile
import dask.array as da
import numpy as np
from dask import delayed


@dataclass
class CziInfo:
    """Stores metadata of a CZI microscopy acquisition.

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

    path: str
    n_t: int
    n_z: int
    n_y: int
    n_x: int
    n_c: int
    dtype: str

    px_size_x: float
    px_size_y: float
    px_size_z: float

    dt_s: float | None
    dt_source: str

    @property
    def voxel(self) -> tuple[float, float, float]:
        """Returns the physical voxel size.

        Returns:
            Voxel size (Z, Y, X) in micrometers.
        """
        return self.px_size_z, self.px_size_y, self.px_size_x


def _parse_iso(value: str) -> datetime:
    """Parse a Zeiss ISO timestamp with seven fractional digits.

    Args:
        value: Timestamp stored in CZI metadata.

    Returns:
        Parsed acquisition timestamp.
    """
    value = value.strip().rstrip("Z")

    if "." in value:
        head, fraction = value.split(".")
        value = f"{head}.{fraction[:6]}"

    return datetime.fromisoformat(value)


class CziSource:
    """
    Provide access to microscopy data from a CZI file.
    """

    def __init__(self, path: str | Path, channel: int = 0):
        """Opens a CZI file and loads its metadata.

        Args:
            path: Path to the CZI file.
            channel: Channel index to read. Defaults to 0.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If required axes are missing or the channel is invalid.
        """
        self.path = Path(path)
        self.channel = channel
        self._lock = threading.Lock()
        self._closed = False

        if not self.path.is_file():
            raise FileNotFoundError(f"CZI file not found: {self.path}")

        self._czi = czifile.CziFile(self.path)

        try:
            scene = self._czi.scenes[0]
            sizes = scene.sizes

            # Reject raw lightfield data without a reconstructed Z axis.
            if "Z" not in sizes and "H" in sizes:
                raise ValueError(
                    "Unsupported CZI data: H axis detected without Z axis. "
                    "Expected a reconstructed 3D volume."
                )

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

            scales = scene.coord_scales

            # Z calibration must be finite.
            if not np.isfinite(scales.get("Z", np.nan)):
                raise ValueError("CZI file is missing valid Z spatial calibration.")

            time_interval, time_source = self._read_dt(sizes.get("T", 1))

            self.info = CziInfo(
                path=str(self.path),
                n_t=sizes.get("T", 1),
                n_z=sizes["Z"],
                n_y=sizes["Y"],
                n_x=sizes["X"],
                n_c=n_channels,
                dtype=str(scene.dtype),
                px_size_x=scales.get("X", np.nan) * meters_to_um,
                px_size_y=scales.get("Y", np.nan) * meters_to_um,
                px_size_z=scales["Z"] * meters_to_um,
                dt_s=time_interval,
                dt_source=time_source,
            )

        except Exception:
            self.close()
            raise

    def _read_dt_increment(self) -> float | None:
        """Read the fixed time increment from CZI metadata."""
        try:
            root = ET.fromstring(self._czi.metadata())

            increment = root.find(".//Information/Image/Dimensions/T/Positions/Interval/Increment")

            if increment is not None and increment.text is not None:
                dt_s = float(increment.text)

                if dt_s > 0:
                    return dt_s

        except ET.ParseError, ValueError, TypeError:
            pass

        return None

    def _read_dt_timestamps(self) -> float | None:
        """Read the median time interval from the TimeStamps attachment."""
        try:
            for attachment in self._czi.attachments():
                if attachment.attachment_entry.name == "TimeStamps":
                    timestamps = np.asarray(attachment.data(), dtype=float)

                    if len(timestamps) > 1:
                        return float(np.median(np.diff(timestamps)))

        except Exception:
            pass

        return None

    def _read_dt_acquisition(self, n_t: int) -> float | None:
        """Calculate the time interval from acquisition timestamps.

        Args:
            n_t: Number of time frames.

        Returns:
            Average time interval in seconds, if available.
        """
        try:
            acquisition_times = {}

            for subblock in self._czi.subblocks():
                entry = subblock.directory_entry
                coordinates = dict(zip(entry.dims, entry.start, strict=True))

                if coordinates.get("Z") != 0:
                    continue

                if coordinates.get("C", 0) != self.channel:
                    continue

                t = coordinates.get("T", 0)

                if t not in (0, n_t - 1):
                    continue

                metadata = subblock.metadata()
                match = re.search(r"<AcquisitionTime>([^<]+)", metadata)

                if match is not None:
                    acquisition_times[t] = _parse_iso(match.group(1))

                if len(acquisition_times) == 2:
                    break

            if len(acquisition_times) == 2:
                span = (acquisition_times[n_t - 1] - acquisition_times[0]).total_seconds()

                if span > 0:
                    return span / (n_t - 1)

        except Exception:
            pass

        return None

    def _read_dt(self, n_t: int) -> tuple[float | None, str]:
        """Read the time interval between consecutive frames.

        Args:
            n_t: Number of time frames.

        Returns:
            Time interval in seconds and its metadata source.
        """
        if n_t < 2:
            return None, "single frame"

        increment = self._read_dt_increment()
        if increment is not None:
            return increment, "metadata (T Increment)"

        timestamps = self._read_dt_timestamps()
        if timestamps is not None:
            return timestamps, "TimeStamps attachment"

        acquisition = self._read_dt_acquisition(n_t)
        if acquisition is not None:
            return acquisition, "AcquisitionTime of volumes"

        return None, "not found"

    def read(self, t: int = 0) -> np.ndarray:
        """Read a single 3D volume at the specified time point.

        Args:
            t: Time point index. Defaults to 0.

        Returns:
            NumPy array containing the selected 3D volume.

        Raises:
            IndexError: If the time point is out of range.
            ValueError: If the CZI file is already closed.
        """
        # Select only axes that are present in the CZI file.
        with self._lock:
            if self._closed:
                raise ValueError("Cannot read from a closed CZI file.")

            # Check that the requested time point exists.
            if t < 0 or t >= self.info.n_t:
                raise IndexError(f"Invalid time point {t}. Available time points: 0-{self.info.n_t - 1}")

            if "T" in self._dims and "C" in self._dims:
                return self._czi.asarray(T=t, C=self.channel)

            if "T" in self._dims:
                return self._czi.asarray(T=t)

            if "C" in self._dims:
                return self._czi.asarray(C=self.channel)

            return self._czi.asarray()

    def as_dask(self) -> da.Array:
        """Create a lazy 4D array of the CZI acquisition.

        Returns:
            Dask array with shape (T, Z, Y, X).
        """
        info = self.info
        shape = (info.n_z, info.n_y, info.n_x)
        frames = [
            da.from_delayed(
                delayed(self.read)(t),
                shape=shape,
                dtype=info.dtype,
            )
            for t in range(info.n_t)
        ]

        return da.stack(frames)

    def close(self) -> None:
        """Close the CZI file and release its resources."""
        with self._lock:
            if not self._closed:
                self._czi.close()
                self._closed = True


def suggest_z_range(vol: np.ndarray) -> tuple[int, int, np.ndarray]:
    """Suggest a useful Z range based on image intensity.

    Args:
        vol: 3D image volume with shape (Z, Y, X).

    Returns:
        Minimum Z index, maximum Z index, and intensity profile.

    Raises:
        ValueError: If the volume has invalid dimensions or is empty.
    """
    if vol.ndim != 3:
        raise ValueError("Expected a 3D volume with shape (Z, Y, X)")

    if any(size == 0 for size in vol.shape):
        raise ValueError("Volume must not be empty")

    n_z = vol.shape[0]

    profile = np.percentile(vol.reshape(n_z, -1), 99, axis=1)

    # A single Z slice cannot define a range.
    if n_z == 1:
        return 0, 0, profile

    threshold = np.percentile(profile, 20) * 1.5
    above_threshold = np.where(profile > threshold)[0]

    z_min = max(0, int(above_threshold[0]) - 1) if len(above_threshold) else 0

    gradient = np.gradient(profile)
    gradient_threshold = np.percentile(gradient, 90)

    z_max = n_z - 1

    for z in range(n_z - 1, n_z // 2, -1):
        if gradient[z] < gradient_threshold:
            z_max = z
            break

    if z_min >= z_max:
        z_min, z_max = 0, n_z - 1

    return z_min, z_max, profile
