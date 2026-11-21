from typing import Any, Self


class FrameRange:
    def __init__(self, first: int, last: int):
        self._first: int = 0
        self._last: int = 0

        self.last = last
        self.first = first

    @classmethod
    def full(cls, n_frames: int) -> Self:
        return cls(0, max(n_frames, 1) - 1)

    @classmethod
    def from_dict(cls, params: dict[str, Any]) -> Self | None:
        first, last = params.get("t0"), params.get("t1")

        if first is None or last is None:
            return None

        return cls(int(first), int(last))

    @property
    def first_display(self) -> int:
        return self._first + 1

    @property
    def last_display(self) -> int:
        return self._last + 1

    @property
    def first(self) -> int:
        return self._first

    @first.setter
    def first(self, value: int):
        self._first = min(value, self._last)

    @property
    def last(self) -> int:
        return self._last

    @last.setter
    def last(self, value: int):
        self._last = max(value, self._first)

    @property
    def count(self) -> int:
        return self.last - self.first + 1

    def to_dict(self) -> dict[str, int]:
        return {"t0": self.first, "t1": self.last}
