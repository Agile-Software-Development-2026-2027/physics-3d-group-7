import time
from collections import deque


class FpsCounter:
    """Sliding-window FPS counter driven by explicit `tick()` calls."""

    def __init__(self, window_seconds: float = 1.0) -> None:
        self._window = window_seconds
        self._timestamps: deque[float] = deque()

    def tick(self) -> None:
        now = time.perf_counter()
        self._timestamps.append(now)
        self._prune(now)

    def fps(self) -> float:
        now = time.perf_counter()
        self._prune(now)
        count = len(self._timestamps)
        if count < 2:
            return 0.0
        elapsed = self._timestamps[-1] - self._timestamps[0]
        return (count - 1) / elapsed if elapsed > 0.0 else 0.0

    def reset(self) -> None:
        self._timestamps.clear()

    def _prune(self, now: float) -> None:
        cutoff = now - self._window
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()
