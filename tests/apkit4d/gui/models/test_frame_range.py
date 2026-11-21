import pytest

from apkit4d.gui.models.frame_range import FrameRange


def test_init_and_properties():
    fr = FrameRange(1, 9)
    assert fr.first == 1
    assert fr.last == 9
    assert fr.first_display == 2
    assert fr.last_display == 10
    assert fr.count == 9


def test_single_frame_range():
    fr = FrameRange(5, 5)
    assert fr.first == 5
    assert fr.last == 5
    assert fr.first_display == 6
    assert fr.last_display == 6
    assert fr.count == 1


def test_init_clamp_inconsistent_bounds():
    fr = FrameRange(10, 4)
    assert fr.first == 4
    assert fr.last == 4
    assert fr.count == 1


@pytest.mark.parametrize(
    ("n_frames", "expected_first", "expected_last", "expected_count"),
    [
        (24, 0, 23, 24),
        (1, 0, 0, 1),
        (0, 0, 0, 1),
        (-5, 0, 0, 1),
    ],
)
def test_full(n_frames, expected_first, expected_last, expected_count):
    fr = FrameRange.full(n_frames)
    assert isinstance(fr, FrameRange)
    assert fr.first == expected_first
    assert fr.last == expected_last
    assert fr.count == expected_count


def test_from_dict_valid():
    fr = FrameRange.from_dict({"t0": "2", "t1": 12, "extra": "ignored"})
    assert fr is not None
    assert fr.first == 2
    assert fr.last == 12


@pytest.mark.parametrize(
    "params",
    [
        {},
        {"t0": 1},
        {"t1": 10},
        {"t0": None, "t1": 10},
        {"t0": 1, "t1": None},
        {"t0": None, "t1": None},
    ],
)
def test_from_dict_missing_or_none_returns_none(params):
    assert FrameRange.from_dict(params) is None


def test_to_dict():
    fr = FrameRange(3, 15)
    assert fr.to_dict() == {"t0": 3, "t1": 15}


def test_set_first_within_range():
    fr = FrameRange(2, 10)
    fr.first = 6
    assert fr.first == 6
    assert fr.last == 10
    assert fr.count == 5


def test_set_first_above_last_clamps_to_last():
    fr = FrameRange(2, 8)
    fr.first = 15
    assert fr.first == 8
    assert fr.last == 8
    assert fr.count == 1


def test_set_last_within_range():
    fr = FrameRange(2, 10)
    fr.last = 7
    assert fr.first == 2
    assert fr.last == 7
    assert fr.count == 6


def test_set_last_below_first_clamps_to_first():
    fr = FrameRange(4, 10)
    fr.last = 1
    assert fr.first == 4
    assert fr.last == 4
    assert fr.count == 1
