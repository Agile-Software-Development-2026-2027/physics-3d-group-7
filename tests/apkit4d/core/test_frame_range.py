from dataclasses import FrozenInstanceError, replace

import pytest

from apkit4d.core.frame_range import FrameRange


def test_init_and_properties():
    fr = FrameRange(1, 9)
    assert fr.start == 1
    assert fr.end == 9
    assert fr.start_display == 2
    assert fr.end_display == 10
    assert fr.count == 9


def test_init_and_properties_with_negative():
    fr = FrameRange(-1, -9)
    assert fr.start == 0
    assert fr.end == 0
    assert fr.start_display == 1
    assert fr.end_display == 1
    assert fr.count == 1


def test_single_frame_range():
    fr = FrameRange(5, 5)
    assert fr.start == 5
    assert fr.end == 5
    assert fr.start_display == 6
    assert fr.end_display == 6
    assert fr.count == 1


def test_init_clamp_inconsistent_bounds():
    fr = FrameRange(10, 4)
    assert fr.start == 4
    assert fr.end == 4
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
    assert fr.start == expected_first
    assert fr.end == expected_last
    assert fr.count == expected_count


def test_from_dict_valid():
    fr = FrameRange.from_dict({FrameRange.START: "2", FrameRange.END: 12, "extra": "ignored"})
    assert fr is not None
    assert fr.start == 2
    assert fr.end == 12


@pytest.mark.parametrize(
    "params",
    [
        {},
        {FrameRange.START: 1},
        {FrameRange.END: 10},
        {FrameRange.START: None, FrameRange.END: 10},
        {FrameRange.START: 1, FrameRange.END: None},
        {FrameRange.START: None, FrameRange.END: None},
    ],
)
def test_from_dict_missing_or_none_returns_none(params):
    assert FrameRange.from_dict(params) is None


def test_to_dict():
    fr = FrameRange(3, 15)
    assert fr.to_dict() == {FrameRange.START: 3, FrameRange.END: 15}


def test_equality_compares_the_frames_and_not_the_identity():
    assert FrameRange(2, 8) == FrameRange(2, 8)
    assert FrameRange(2, 8) != FrameRange(2, 9)
    assert FrameRange(2, 8) != FrameRange(3, 8)


def test_equality_with_other_types_is_false():
    assert FrameRange(2, 8) != (2, 8)
    assert FrameRange(2, 8) != {FrameRange.START: 2, FrameRange.END: 8}
    assert FrameRange(2, 8) is not None


def test_repr_shows_the_frames():
    assert repr(FrameRange(2, 8)) == "FrameRange(start=2, end=8)"


def test_dict_round_trip_keeps_the_frames():
    original = FrameRange(3, 15)

    assert FrameRange.from_dict(original.to_dict()) == original


def test_start_above_end_is_brought_down_to_the_end():
    assert FrameRange(15, 8) == FrameRange(8, 8)
    assert FrameRange(15, 8).count == 1


def test_a_range_cannot_be_changed():
    fr = FrameRange(2, 8)

    with pytest.raises(FrozenInstanceError):
        fr.start = 4  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        fr.end = 6  # type: ignore[misc]

    assert fr == FrameRange(2, 8)


def test_a_range_can_be_used_as_a_key():
    assert {FrameRange(2, 8): "chosen"}[FrameRange(2, 8)] == "chosen"
    assert len({FrameRange(2, 8), FrameRange(2, 8), FrameRange(2, 9)}) == 2


def test_with_start_within_range():
    fr = FrameRange(2, 10).with_start(6)

    assert fr.start == 6
    assert fr.end, fr.count == 10
    assert fr.count == 5


def test_with_start_above_end_clamps_to_end():
    fr = FrameRange(2, 8).with_start(15)

    assert fr.start == 8
    assert fr.end == 8
    assert fr.count == 1


def test_with_start_cannot_be_negative():
    fr = FrameRange(2, 8).with_start(-15)

    assert fr.start == 0
    assert fr.end == 8
    assert fr.count == 9


def test_with_end_within_range():
    fr = FrameRange(2, 10).with_end(7)

    assert fr.start == 2
    assert fr.end == 7
    assert fr.count == 6


def test_with_end_below_start_clamps_to_first():
    fr = FrameRange(4, 10).with_end(1)

    assert fr.start == 4
    assert fr.end == 4
    assert fr.count == 1


def test_with_end_cannot_be_negative():
    fr = FrameRange(4, 10).with_end(-1)

    assert fr.start == 4
    assert fr.end == 4
    assert fr.count == 1


def test_replace_goes_through_the_constructor_and_follows_its_rule():
    # 'replace' cannot tell which frame was changed, so it cannot tell what to clamp.
    # This is why it follows the constructor rule: start is clamped to end
    assert replace(FrameRange(4, 10), end=1) == FrameRange(4, 1) == FrameRange(1, 1)


def test_changing_a_frame_does_not_change_the_original():
    original = FrameRange(2, 8)

    changed = original.with_start(4).with_end(6)

    assert original == FrameRange(2, 8)
    assert (changed.start_display, changed.end_display) == (5, 7)


@pytest.mark.parametrize(
    ("outer", "inner", "expected"),
    [
        (FrameRange(0, 100), FrameRange(10, 50), True),
        (FrameRange(0, 100), FrameRange(0, 100), True),
        (FrameRange(0, 100), FrameRange(0, 50), True),
        (FrameRange(0, 100), FrameRange(50, 100), True),
        (FrameRange(0, 100), FrameRange(50, 50), True),
        (FrameRange(0, 100), FrameRange(-1, 50), True),
        (FrameRange(0, 100), FrameRange(50, 101), False),
        (FrameRange(0, 100), FrameRange(-1, 101), False),
        (FrameRange(0, 100), FrameRange(-10, 10), True),
        (FrameRange(0, 100), FrameRange(90, 110), False),
        (FrameRange(0, 100), FrameRange(110, 200), False),
        (FrameRange(10, 50), FrameRange(0, 100), False),
    ],
)
def test_frame_range_contains(
    outer: FrameRange,
    inner: FrameRange,
    expected: bool,
):
    assert outer.contains(inner) is expected


@pytest.mark.parametrize(
    ("value", "bounds", "expected"),
    [
        ((11, 16), (6, 25), (11, 16)),  # already inside: untouched
        ((11, 16), (11, 16), (11, 16)),  # same as the bounds
        ((11, 16), (13, 19), (13, 16)),  # start cut
        ((11, 16), (9, 14), (11, 14)),  # end cut
        ((11, 16), (13, 14), (13, 14)),  # both ends cut
        ((11, 13), (15, 19), (15, 15)),  # entirely before the bounds
        ((16, 19), (9, 12), (12, 12)),  # entirely after the bounds
        ((11, 11), (11, 11), (11, 11)),  # single frame, single-frame bounds
        ((5, 5), (9, 19), (9, 9)),  # single frame before the bounds
        ((25, 25), (9, 19), (19, 19)),  # single frame after the bounds
    ],
)
def test_clamp(value, bounds, expected):
    assert FrameRange(*value).clamp(FrameRange(*bounds)) == FrameRange(*expected)
