"""Tests for the in-memory frame cache."""

import numpy as np
import pytest

from apkit4d.gui.models.frame_cache import FrameCache


def test_store_and_retrieve_frame() -> None:
    cache = FrameCache(max_bytes=100)
    volume = np.zeros((2, 3, 4), dtype=np.uint8)

    assert cache.put(0, volume)
    assert cache.get(0) is volume
    assert cache.size_bytes == volume.nbytes
    assert len(cache) == 1


def test_missing_frame() -> None:
    cache = FrameCache(max_bytes=100)

    assert cache.get(0) is None


def test_lru_eviction() -> None:
    volume = np.zeros((2, 3, 4), dtype=np.uint8)
    cache = FrameCache(max_bytes=2 * volume.nbytes)

    cache.put(0, volume.copy())
    cache.put(1, volume.copy())

    cache.get(0)
    cache.put(2, volume.copy())

    assert cache.get(0) is not None
    assert cache.get(1) is None
    assert cache.get(2) is not None
    assert len(cache) == 2
    assert cache.size_bytes == 2 * volume.nbytes


def test_replace_frame() -> None:
    cache = FrameCache(max_bytes=100)
    original = np.zeros(20, dtype=np.uint8)
    replacement = np.zeros(30, dtype=np.uint8)

    cache.put(0, original)
    cache.put(0, replacement)

    assert cache.get(0) is replacement
    assert cache.size_bytes == replacement.nbytes
    assert len(cache) == 1


def test_reject_oversized_frame() -> None:
    cache = FrameCache(max_bytes=10)
    volume = np.zeros(20, dtype=np.uint8)

    assert not cache.put(0, volume)
    assert cache.get(0) is None
    assert cache.size_bytes == 0


def test_reduce_cache_limit() -> None:
    volume = np.zeros(20, dtype=np.uint8)
    cache = FrameCache(max_bytes=60)

    for frame in range(3):
        cache.put(frame, volume.copy())

    cache.set_limit(20)

    assert cache.max_bytes == 20
    assert cache.size_bytes == 20
    assert len(cache) == 1
    assert cache.get(2) is not None


def test_zero_cache_limit() -> None:
    cache = FrameCache(max_bytes=100)
    volume = np.zeros(20, dtype=np.uint8)

    cache.put(0, volume)
    cache.set_limit(0)

    assert len(cache) == 0
    assert cache.size_bytes == 0
    assert not cache.put(0, volume)


def test_clear_cache() -> None:
    cache = FrameCache(max_bytes=100)
    cache.put(0, np.zeros(20, dtype=np.uint8))

    cache.clear()

    assert len(cache) == 0
    assert cache.size_bytes == 0
    assert cache.get(0) is None
    assert cache.max_bytes == 100


def test_negative_cache_limit() -> None:
    with pytest.raises(ValueError):
        FrameCache(max_bytes=-1)
