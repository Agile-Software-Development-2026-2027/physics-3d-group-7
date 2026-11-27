"""Tests for the frame cache memory policy."""

from types import SimpleNamespace

import pytest

from apkit4d.gui.models.frame_cache_policy import (
    BYTES_PER_GB,
    calculate_cache_limit,
)
from apkit4d.gui.models.frame_loading_config import (
    FrameLoadingConfig,
    FrameLoadingMode,
)


@pytest.fixture
def mock_memory(monkeypatch):
    def set_memory(total_gb: int, available_gb: int) -> None:
        monkeypatch.setattr(
            "psutil.virtual_memory",
            lambda: SimpleNamespace(
                total=total_gb * BYTES_PER_GB,
                available=available_gb * BYTES_PER_GB,
            ),
        )

    return set_memory


def test_lazy_loading(mock_memory) -> None:
    mock_memory(64, 32)
    config = FrameLoadingConfig(mode=FrameLoadingMode.LAZY)

    assert calculate_cache_limit(config, 0, 32 * BYTES_PER_GB) == 0


@pytest.mark.parametrize(
    "mode",
    [FrameLoadingMode.AUTOMATIC, FrameLoadingMode.FULL],
)
def test_dynamic_limit(mock_memory, mode) -> None:
    mock_memory(100, 60)
    config = FrameLoadingConfig(
        mode=mode,
        memory_reserve_percent=20,
    )

    assert calculate_cache_limit(config, 0, 60 * BYTES_PER_GB) == 40 * BYTES_PER_GB


def test_existing_cache_is_accounted_for(mock_memory) -> None:
    mock_memory(100, 30)
    config = FrameLoadingConfig(memory_reserve_percent=20)

    assert calculate_cache_limit(config, 10 * BYTES_PER_GB, 40 * BYTES_PER_GB) == 20 * BYTES_PER_GB


def test_manual_limit(mock_memory) -> None:
    mock_memory(100, 60)
    config = FrameLoadingConfig(
        mode=FrameLoadingMode.MANUAL,
        cache_limit_gb=8,
        memory_reserve_percent=20,
    )

    assert calculate_cache_limit(config, 0, 60 * BYTES_PER_GB) == 8 * BYTES_PER_GB


def test_manual_limit_respects_available_memory(mock_memory) -> None:
    mock_memory(100, 25)
    config = FrameLoadingConfig(
        mode=FrameLoadingMode.MANUAL,
        cache_limit_gb=32,
        memory_reserve_percent=20,
    )

    assert calculate_cache_limit(config, 0, 60 * BYTES_PER_GB) == 5 * BYTES_PER_GB


def test_insufficient_memory(mock_memory) -> None:
    mock_memory(100, 10)
    config = FrameLoadingConfig(memory_reserve_percent=20)

    assert calculate_cache_limit(config, 0, 60 * BYTES_PER_GB) == 0


def test_memory_pressure_reduces_limit(mock_memory) -> None:
    mock_memory(100, 15)
    config = FrameLoadingConfig(memory_reserve_percent=20)

    assert calculate_cache_limit(config, 10 * BYTES_PER_GB, 60 * BYTES_PER_GB) == 5 * BYTES_PER_GB


def test_large_memory_workstation(mock_memory) -> None:
    mock_memory(512, 480)
    config = FrameLoadingConfig(
        mode=FrameLoadingMode.FULL,
        memory_reserve_percent=10,
    )

    assert calculate_cache_limit(config, 0, 480 * BYTES_PER_GB) == 428_800_000_000


def test_initial_budget_prevents_excessive_growth(mock_memory) -> None:
    mock_memory(24, 8)
    config = FrameLoadingConfig(memory_reserve_percent=20)

    assert calculate_cache_limit(config, 20 * BYTES_PER_GB, 10 * BYTES_PER_GB) == 5_200_000_000


def test_cache_limit_recovers_after_memory_pressure(mock_memory) -> None:
    config = FrameLoadingConfig(memory_reserve_percent=20)
    initial_available = 60 * BYTES_PER_GB

    mock_memory(100, 15)

    assert calculate_cache_limit(config, 10 * BYTES_PER_GB, initial_available) == 5 * BYTES_PER_GB

    mock_memory(100, 55)

    assert calculate_cache_limit(config, 5 * BYTES_PER_GB, initial_available) == 40 * BYTES_PER_GB


def test_memory_reserve_change(mock_memory) -> None:
    mock_memory(100, 30)
    initial_available = 60 * BYTES_PER_GB
    cached_bytes = 30 * BYTES_PER_GB

    for reserve, expected in [(1, 59), (20, 40), (1, 59)]:
        config = FrameLoadingConfig(
            memory_reserve_percent=reserve,
        )

        assert calculate_cache_limit(config, cached_bytes, initial_available) == expected * BYTES_PER_GB
