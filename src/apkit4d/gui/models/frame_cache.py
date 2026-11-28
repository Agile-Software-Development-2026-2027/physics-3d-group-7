"""In-memory cache for loaded frames."""

from collections import OrderedDict

from numpy.typing import NDArray


class FrameCache:
    """Store loaded frames using a least recently used eviction policy."""

    def __init__(self, max_bytes: int) -> None:
        self._frames: OrderedDict[int, NDArray] = OrderedDict()
        self._size_bytes = 0
        self.set_limit(max_bytes)

    @property
    def size_bytes(self) -> int:
        """Total size of cached frame data in bytes."""
        return self._size_bytes

    @property
    def max_bytes(self) -> int:
        """Maximum allowed cache size in bytes."""
        return self._max_bytes

    def __len__(self) -> int:
        """Return the number of cached frames."""
        return len(self._frames)

    def get(self, frame: int) -> NDArray | None:
        """Return a cached frame and mark it as recently used."""
        volume = self._frames.get(frame)

        if volume is not None:
            self._frames.move_to_end(frame)

        return volume

    def put(self, frame: int, volume: NDArray) -> bool:
        """Store a frame if it fits within the cache limit."""
        if volume.nbytes > self._max_bytes:
            return False

        previous = self._frames.pop(frame, None)

        if previous is not None:
            self._size_bytes -= previous.nbytes

        self._frames[frame] = volume
        self._size_bytes += volume.nbytes

        self._evict()
        return True

    def set_limit(self, max_bytes: int) -> None:
        """Update the cache limit and evict frames if necessary."""
        if max_bytes < 0:
            raise ValueError("Cache limit cannot be negative.")

        self._max_bytes = max_bytes
        self._evict()

    def clear(self) -> None:
        """Remove all cached frames."""
        self._frames.clear()
        self._size_bytes = 0

    def _evict(self) -> None:
        """Remove least recently used frames until the limit is met."""
        while self._size_bytes > self._max_bytes:
            _, volume = self._frames.popitem(last=False)
            self._size_bytes -= volume.nbytes
