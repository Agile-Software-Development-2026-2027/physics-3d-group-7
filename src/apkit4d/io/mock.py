"""Synthetic microscopy dataset and FrameSource implementation for GUI development and demos."""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from numpy.typing import NDArray

from apkit4d.blob_detection import DETECTION_COLUMNS
from apkit4d.io.czi import CziInfo

logger = logging.getLogger(__name__)

MOCK_TRACK_COLUMNS: list[str] = [
    *DETECTION_COLUMNS,
    "t_s",
    "reliability",
    "margin_sigma",
    "candidate_count",
    "track_id",
]


@dataclass(frozen=True)
class MockConfig:
    """Configuration for generating a synthetic 3D+T algae tracking dataset.

    Attributes:
        n_t: Number of time frames.
        n_z: Volume depth in voxels.
        n_y: Volume height in voxels.
        n_x: Volume width in voxels.
        px_size_x: Voxel spacing along X in micrometers.
        px_size_y: Voxel spacing along Y in micrometers.
        px_size_z: Voxel spacing along Z in micrometers.
        dt_s: Time interval between consecutive frames in seconds.
        seed: Random seed for reproducible noise and particle intensities.
    """

    n_t: int = 120
    n_z: int = 20
    n_y: int = 120
    n_x: int = 120
    px_size_x: float = 2.8
    px_size_y: float = 2.8
    px_size_z: float = 18.0
    dt_s: float = 0.05
    seed: int = 42


@dataclass(frozen=True)
class _TrackBlueprint:
    """Parametric definition of a synthetic swimmer trajectory inside normalized domain space."""

    track_id: int
    profile: str
    start_frac: tuple[float, float, float]
    end_frac: tuple[float, float, float]
    radius_um: float
    omega_rad_s: float
    phase_rad: float = 0.0
    sway_frac: tuple[float, float, float] = (0.0, 0.0, 0.0)
    speed_mod: float = 0.0
    start_frac_t: float = 0.0
    end_frac_t: float = 1.0
    drop_frac_window: tuple[float, float] | None = None
    peak_intensity: float = 2400.0


def _build_default_blueprints() -> tuple[_TrackBlueprint, ...]:
    """Return a diverse set of helical, smooth, peripheral, and transient tracks."""
    return (
        # Tight helices passing through central and mid volume
        _TrackBlueprint(
            track_id=1,
            profile="tight_helix",
            start_frac=(0.24, 0.28, 0.25),
            end_frac=(0.76, 0.72, 0.78),
            radius_um=8.5,
            omega_rad_s=13.0,
            phase_rad=0.0,
            speed_mod=0.25,
            peak_intensity=3100.0,
        ),
        _TrackBlueprint(
            track_id=2,
            profile="tight_helix",
            start_frac=(0.72, 0.25, 0.72),
            end_frac=(0.28, 0.74, 0.28),
            radius_um=10.0,
            omega_rad_s=11.0,
            phase_rad=1.2,
            speed_mod=0.15,
            peak_intensity=2850.0,
        ),
        _TrackBlueprint(
            track_id=3,
            profile="tight_helix",
            start_frac=(0.35, 0.65, 0.20),
            end_frac=(0.68, 0.35, 0.84),
            radius_um=7.5,
            omega_rad_s=15.0,
            phase_rad=2.4,
            peak_intensity=2700.0,
        ),
        _TrackBlueprint(
            track_id=4,
            profile="tight_helix",
            start_frac=(0.50, 0.22, 0.45),
            end_frac=(0.52, 0.78, 0.56),
            radius_um=9.5,
            omega_rad_s=-12.0,
            phase_rad=0.7,
            peak_intensity=2950.0,
        ),
        # Wide helices with slower rotational frequency
        _TrackBlueprint(
            track_id=5,
            profile="wide_helix",
            start_frac=(0.25, 0.50, 0.32),
            end_frac=(0.75, 0.52, 0.72),
            radius_um=27.0,
            omega_rad_s=4.2,
            phase_rad=0.4,
            speed_mod=0.35,
            peak_intensity=3250.0,
        ),
        _TrackBlueprint(
            track_id=6,
            profile="wide_helix",
            start_frac=(0.65, 0.72, 0.28),
            end_frac=(0.32, 0.28, 0.75),
            radius_um=24.0,
            omega_rad_s=5.0,
            phase_rad=2.0,
            peak_intensity=2900.0,
        ),
        _TrackBlueprint(
            track_id=7,
            profile="wide_helix",
            start_frac=(0.30, 0.32, 0.68),
            end_frac=(0.74, 0.68, 0.30),
            radius_um=31.0,
            omega_rad_s=-3.6,
            phase_rad=3.1,
            speed_mod=0.2,
            peak_intensity=2650.0,
        ),
        # Non-helical smooth / curved / ballistic tracks
        _TrackBlueprint(
            track_id=8,
            profile="linear",
            start_frac=(0.18, 0.48, 0.52),
            end_frac=(0.84, 0.54, 0.48),
            radius_um=0.0,
            omega_rad_s=0.0,
            speed_mod=0.55,
            peak_intensity=3000.0,
        ),
        _TrackBlueprint(
            track_id=9,
            profile="smooth_curve",
            start_frac=(0.28, 0.20, 0.35),
            end_frac=(0.70, 0.80, 0.68),
            radius_um=0.0,
            omega_rad_s=0.0,
            sway_frac=(0.10, -0.08, 0.06),
            speed_mod=0.3,
            peak_intensity=2500.0,
        ),
        _TrackBlueprint(
            track_id=10,
            profile="slow_drift",
            start_frac=(0.45, 0.44, 0.58),
            end_frac=(0.58, 0.58, 0.46),
            radius_um=0.0,
            omega_rad_s=0.0,
            sway_frac=(0.04, 0.05, -0.03),
            peak_intensity=2100.0,
        ),
        _TrackBlueprint(
            track_id=11,
            profile="smooth_curve",
            start_frac=(0.76, 0.62, 0.24),
            end_frac=(0.24, 0.38, 0.78),
            radius_um=0.0,
            omega_rad_s=0.0,
            sway_frac=(-0.09, 0.11, 0.04),
            peak_intensity=2600.0,
        ),
        # Peripheral tracks staying outside a typical central ROI (useful for filtering tests)
        _TrackBlueprint(
            track_id=12,
            profile="peripheral_helix",
            start_frac=(0.08, 0.12, 0.25),
            end_frac=(0.14, 0.86, 0.75),
            radius_um=8.0,
            omega_rad_s=11.5,
            phase_rad=0.5,
            peak_intensity=2300.0,
        ),
        _TrackBlueprint(
            track_id=13,
            profile="peripheral_curve",
            start_frac=(0.86, 0.14, 0.72),
            end_frac=(0.90, 0.88, 0.28),
            radius_um=0.0,
            omega_rad_s=0.0,
            sway_frac=(-0.03, 0.0, 0.05),
            peak_intensity=2200.0,
        ),
        _TrackBlueprint(
            track_id=14,
            profile="peripheral_helix",
            start_frac=(0.16, 0.88, 0.30),
            end_frac=(0.84, 0.91, 0.70),
            radius_um=9.0,
            omega_rad_s=-10.0,
            phase_rad=1.7,
            peak_intensity=2450.0,
        ),
        # Transient & gapped tracks testing entry, exit, and missing frames
        _TrackBlueprint(
            track_id=15,
            profile="transient_early",
            start_frac=(0.30, 0.75, 0.42),
            end_frac=(0.66, 0.40, 0.64),
            radius_um=11.0,
            omega_rad_s=9.5,
            start_frac_t=0.0,
            end_frac_t=0.48,
            peak_intensity=2550.0,
        ),
        _TrackBlueprint(
            track_id=16,
            profile="transient_late",
            start_frac=(0.64, 0.30, 0.36),
            end_frac=(0.34, 0.70, 0.72),
            radius_um=14.0,
            omega_rad_s=7.0,
            start_frac_t=0.35,
            end_frac_t=1.0,
            peak_intensity=2750.0,
        ),
        _TrackBlueprint(
            track_id=17,
            profile="gapped_transient",
            start_frac=(0.40, 0.30, 0.66),
            end_frac=(0.62, 0.70, 0.38),
            radius_um=0.0,
            omega_rad_s=0.0,
            sway_frac=(0.06, -0.04, 0.05),
            start_frac_t=0.18,
            end_frac_t=0.82,
            drop_frac_window=(0.45, 0.48),
            peak_intensity=2350.0,
        ),
    )


def _orthonormal_basis(axis: NDArray[np.float64]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Build two unit vectors orthogonal to `axis`."""
    norm = float(np.linalg.norm(axis))
    unit_axis = np.array([1.0, 0.0, 0.0], dtype=np.float64) if norm < 1e-9 else axis / norm
    ref = (
        np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if abs(float(unit_axis[2])) < 0.9
        else np.array([0.0, 1.0, 0.0], dtype=np.float64)
    )
    e1 = np.cross(unit_axis, ref)
    e1 /= float(np.linalg.norm(e1))
    e2 = np.cross(unit_axis, e1)
    return e1, e2


def _evaluate_blueprint(
    spec: _TrackBlueprint,
    config: MockConfig,
    domain_um: NDArray[np.float64],
    margin_um: NDArray[np.float64],
) -> pd.DataFrame:
    """Sample a single `_TrackBlueprint` into trajectory points strictly within domain bounds."""
    t_start = max(0, int(round(spec.start_frac_t * (config.n_t - 1))))
    t_end = min(config.n_t - 1, int(round(spec.end_frac_t * (config.n_t - 1))))
    if t_end <= t_start:
        t_end = min(config.n_t - 1, t_start + 1)

    frames = np.arange(t_start, t_end + 1, dtype=np.int64)
    if spec.drop_frac_window is not None and len(frames) > 4:
        drop_lo = int(round(spec.drop_frac_window[0] * (config.n_t - 1)))
        drop_hi = int(round(spec.drop_frac_window[1] * (config.n_t - 1)))
        keep_mask = (frames < drop_lo) | (frames > drop_hi)
        if np.count_nonzero(keep_mask) >= 2:
            frames = frames[keep_mask]

    span_frames = max(1, t_end - t_start)
    s = (frames - t_start) / float(span_frames)
    mod = float(np.clip(spec.speed_mod, -0.65, 0.65))
    progress = s + (mod / (2.0 * np.pi)) * np.sin(2.0 * np.pi * s)

    usable_span = np.maximum(domain_um - 2.0 * margin_um, 1e-3)
    max_safe_radius = float(np.min(usable_span) * 0.28)
    radius = min(spec.radius_um, max_safe_radius)

    inner_min = margin_um + radius
    inner_max = np.maximum(domain_um - margin_um - radius, inner_min)
    inner_span = inner_max - inner_min

    p_start = inner_min + np.array(spec.start_frac, dtype=np.float64) * inner_span
    p_end = inner_min + np.array(spec.end_frac, dtype=np.float64) * inner_span
    sway = np.array(spec.sway_frac, dtype=np.float64) * inner_span

    center = p_start[None, :] + progress[:, None] * (p_end - p_start)[None, :]
    center += np.sin(np.pi * progress)[:, None] * sway[None, :]

    if radius > 0.0 and spec.omega_rad_s != 0.0:
        e1, e2 = _orthonormal_basis(p_end - p_start)
        t_sec = (frames - t_start).astype(np.float64) * config.dt_s
        angle = spec.omega_rad_s * t_sec + spec.phase_rad
        helix_offset = radius * (np.cos(angle)[:, None] * e1[None, :] + np.sin(angle)[:, None] * e2[None, :])
        coords_um = center + helix_offset
    else:
        coords_um = center

    coords_um = np.clip(coords_um, margin_um[None, :], (domain_um - margin_um)[None, :])

    x_um = coords_um[:, 0]
    y_um = coords_um[:, 1]
    z_um = coords_um[:, 2]

    n_pts = len(frames)
    return pd.DataFrame(
        {
            "frame": frames,
            "label": np.ones(n_pts, dtype=np.int32),
            "z": z_um / config.px_size_z,
            "y": y_um / config.px_size_y,
            "x": x_um / config.px_size_x,
            "z_um": z_um,
            "y_um": y_um,
            "x_um": x_um,
            "volume_um3": np.full(n_pts, 1850.0, dtype=np.float64),
            "n_voxels": np.full(n_pts, 13, dtype=np.int64),
            "z_extent": np.full(n_pts, config.px_size_z * 2.5, dtype=np.float64),
            "response": np.full(n_pts, 0.72, dtype=np.float64),
            "peak": np.full(n_pts, spec.peak_intensity, dtype=np.float64),
            "mean_intensity": np.full(n_pts, spec.peak_intensity * 0.42, dtype=np.float64),
            "max_intensity": np.full(n_pts, spec.peak_intensity, dtype=np.float64),
            "t_s": frames.astype(np.float64) * config.dt_s,
            "reliability": np.full(n_pts, 0.98, dtype=np.float64),
            "margin_sigma": np.full(n_pts, 4.5, dtype=np.float64),
            "candidate_count": np.ones(n_pts, dtype=np.int32),
            "track_id": np.full(n_pts, spec.track_id, dtype=np.int32),
        }
    )


def generate_mock_tracks(config: MockConfig | None = None) -> tuple[pd.DataFrame, dict[int, str]]:
    """Generate a synthetic tracks DataFrame matching ParticleLinker output schema.

    Args:
        config: Volume geometry and timing configuration. Uses default `MockConfig` if None.

    Returns:
        Tuple of `(tracks_df, motion_profiles)` where `tracks_df` contains
        `MOCK_TRACK_COLUMNS` sorted by `["track_id", "frame"]` and `motion_profiles`
        maps each `track_id` to its trajectory archetype name.
    """
    cfg = config if config is not None else MockConfig()
    if cfg.n_t < 2:
        raise ValueError(f"MockConfig.n_t must be >= 2, got {cfg.n_t}")

    domain_um = np.array(
        [
            max(1, cfg.n_x - 1) * cfg.px_size_x,
            max(1, cfg.n_y - 1) * cfg.px_size_y,
            max(1, cfg.n_z - 1) * cfg.px_size_z,
        ],
        dtype=np.float64,
    )
    margin_um = np.minimum(
        np.array([2.0 * cfg.px_size_x, 2.0 * cfg.px_size_y, 1.25 * cfg.px_size_z], dtype=np.float64),
        domain_um * 0.2,
    )

    blueprints = _build_default_blueprints()
    frames_list = [_evaluate_blueprint(bp, cfg, domain_um, margin_um) for bp in blueprints]
    tracks = pd.concat(frames_list, ignore_index=True)

    # Assign unique per-frame segmentation labels (1..K) sorted cleanly
    tracks = tracks.sort_values(["frame", "track_id"]).reset_index(drop=True)
    tracks["label"] = (tracks.groupby("frame").cumcount() + 1).astype(np.int32)
    tracks = tracks.sort_values(["track_id", "frame"]).reset_index(drop=True)
    tracks = tracks[MOCK_TRACK_COLUMNS]

    profiles = {bp.track_id: bp.profile for bp in blueprints}
    return tracks, profiles


class MockFrameSource:
    """In-memory synthetic FrameSource aligned with generated 3D algae trajectories.

    Synthesizes 3D Gaussian blobs in each requested frame on demand so memory footprint
    stays minimal while providing full volume playback, preprocessing, and blob alignment.
    """

    BACKGROUND_LEVEL = 120.0
    NOISE_STD = 12.0
    SIGMA_XY_VOX = 1.8
    SIGMA_Z_VOX = 1.2

    def __init__(self, config: MockConfig | None = None, name: str = "Mock Algae Session") -> None:
        self._config = config if config is not None else MockConfig()
        self._closed = False
        self._tracks, self._profiles = generate_mock_tracks(self._config)
        self._info = CziInfo(
            path=name,
            n_t=self._config.n_t,
            n_z=self._config.n_z,
            n_y=self._config.n_y,
            n_x=self._config.n_x,
            n_c=1,
            dtype="uint16",
            px_size_x=self._config.px_size_x,
            px_size_y=self._config.px_size_y,
            px_size_z=self._config.px_size_z,
            dt_s=self._config.dt_s,
            dt_source="mock",
        )

        # Index per-frame detections once for O(1) lookup inside read(t)
        self._frame_blobs: dict[int, tuple[NDArray[np.float64], ...]] = {}
        for _frame_key, group in self._tracks.groupby("frame", sort=False):
            frame_num = int(group["frame"].iloc[0])
            self._frame_blobs[frame_num] = (
                group["z"].to_numpy(dtype=np.float64),
                group["y"].to_numpy(dtype=np.float64),
                group["x"].to_numpy(dtype=np.float64),
                group["peak"].to_numpy(dtype=np.float64),
            )

        summary = self.summary()
        logger.info(
            "Initialized MockFrameSource: frames=%d, shape=(%d, %d, %d), tracks=%d, detections=%d",
            self._info.n_t,
            self._info.n_z,
            self._info.n_y,
            self._info.n_x,
            summary["n_tracks"],
            summary["n_detections"],
        )

    @property
    def info(self) -> CziInfo:
        """Acquisition metadata describing shape, spacing, and frame rate."""
        return self._info

    @property
    def tracks(self) -> pd.DataFrame:
        """Copy of the precomputed synthetic trajectories DataFrame."""
        return self._tracks.copy()

    @property
    def motion_profiles(self) -> dict[int, str]:
        """Mapping from `track_id` to its motion archetype label."""
        return dict(self._profiles)

    def summary(self) -> dict[str, Any]:
        """Return diagnostic summary metrics for inspecting mock dataset state."""
        speeds: list[float] = []
        for _, grp in self._tracks.groupby("track_id", sort=False):
            coords = grp[["x_um", "y_um", "z_um"]].to_numpy(dtype=np.float64)
            t_sec = grp["t_s"].to_numpy(dtype=np.float64)
            if len(coords) > 1:
                dt = np.diff(t_sec)
                valid = dt > 0
                if np.any(valid):
                    disp = np.linalg.norm(np.diff(coords, axis=0), axis=1)
                    speeds.extend((disp[valid] / dt[valid]).tolist())

        speed_arr = np.asarray(speeds, dtype=np.float64)
        return {
            "n_t": self._info.n_t,
            "shape_zyx": (self._info.n_z, self._info.n_y, self._info.n_x),
            "voxel_um_zyx": self._info.voxel,
            "dt_s": self._info.dt_s,
            "n_tracks": int(self._tracks["track_id"].nunique()),
            "n_detections": int(len(self._tracks)),
            "profiles": dict(self._profiles),
            "bounds_um": {
                "x": (float(self._tracks["x_um"].min()), float(self._tracks["x_um"].max())),
                "y": (float(self._tracks["y_um"].min()), float(self._tracks["y_um"].max())),
                "z": (float(self._tracks["z_um"].min()), float(self._tracks["z_um"].max())),
            },
            "speed_um_s": {
                "min": float(speed_arr.min()) if len(speed_arr) else 0.0,
                "mean": float(speed_arr.mean()) if len(speed_arr) else 0.0,
                "max": float(speed_arr.max()) if len(speed_arr) else 0.0,
            },
        }

    def read(self, t: int) -> NDArray[np.uint16]:
        """Synthesize and return the 3D `(Z, Y, X)` volume for frame `t`."""
        if self._closed:
            raise RuntimeError("Cannot read from a closed MockFrameSource")
        if t < 0 or t >= self._info.n_t:
            raise IndexError(f"Frame index {t} out of range [0, {self._info.n_t})")

        rng = np.random.default_rng(self._config.seed + t)
        volume = self.BACKGROUND_LEVEL + rng.normal(
            0.0,
            self.NOISE_STD,
            size=(self._info.n_z, self._info.n_y, self._info.n_x),
        )

        blobs = self._frame_blobs.get(t)
        if blobs is not None:
            rad_z = int(np.ceil(3.0 * self.SIGMA_Z_VOX))
            rad_xy = int(np.ceil(3.0 * self.SIGMA_XY_VOX))
            zs, ys, xs, peaks = blobs
            for zc, yc, xc, peak in zip(zs, ys, xs, peaks, strict=True):
                z0 = max(0, int(np.floor(zc)) - rad_z)
                z1 = min(self._info.n_z, int(np.ceil(zc)) + rad_z + 1)
                y0 = max(0, int(np.floor(yc)) - rad_xy)
                y1 = min(self._info.n_y, int(np.ceil(yc)) + rad_xy + 1)
                x0 = max(0, int(np.floor(xc)) - rad_xy)
                x1 = min(self._info.n_x, int(np.ceil(xc)) + rad_xy + 1)

                gz = ((np.arange(z0, z1, dtype=np.float64) - zc) / self.SIGMA_Z_VOX) ** 2
                gy = ((np.arange(y0, y1, dtype=np.float64) - yc) / self.SIGMA_XY_VOX) ** 2
                gx = ((np.arange(x0, x1, dtype=np.float64) - xc) / self.SIGMA_XY_VOX) ** 2
                gauss = peak * np.exp(-0.5 * (gz[:, None, None] + gy[None, :, None] + gx[None, None, :]))
                volume[z0:z1, y0:y1, x0:x1] += gauss

        return np.clip(volume, 0.0, 65535.0).astype(np.uint16)

    def close(self) -> None:
        """Mark the mock source as closed."""
        self._closed = True


def create_mock_source(config: MockConfig | None = None) -> MockFrameSource:
    """Create a `MockFrameSource` instance for CLI `--mock` startup or tests."""
    return MockFrameSource(config=config)
