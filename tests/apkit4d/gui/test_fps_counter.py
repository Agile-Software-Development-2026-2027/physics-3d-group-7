import pytest

from apkit4d.gui.fps_counter import FpsCounter


def test_fps_counter_initial_and_single_tick_return_zero(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr("time.perf_counter", lambda: now)

    counter = FpsCounter(window_seconds=1.0)
    assert counter.fps() == 0.0

    counter.tick()
    assert counter.fps() == 0.0


def test_fps_counter_computes_rate_and_prunes_old_samples(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr("time.perf_counter", lambda: now)

    counter = FpsCounter(window_seconds=1.0)
    # 5 ticks spaced by 0.25 s over 1.0 s -> (5 - 1) / 1.0 = 4.0 FPS
    for i in range(5):
        now = 100.0 + i * 0.25
        counter.tick()

    assert counter.fps() == pytest.approx(4.0)

    # Advance past the 1.0 s sliding window so all timestamps expire
    now = 102.5
    assert counter.fps() == 0.0


def test_fps_counter_reset_clears_history(monkeypatch) -> None:
    now = 100.0
    monkeypatch.setattr("time.perf_counter", lambda: now)

    counter = FpsCounter(window_seconds=1.0)
    counter.tick()
    now = 100.1
    counter.tick()
    assert counter.fps() == pytest.approx(10.0)

    counter.reset()
    assert counter.fps() == 0.0
