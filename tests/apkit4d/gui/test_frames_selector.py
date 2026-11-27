import pytest
from PySide6.QtWidgets import QLabel

from apkit4d.core.frame_range import FrameRange
from apkit4d.gui.constants import texts
from apkit4d.gui.views.widgets.frames_selector import FramesSelector


@pytest.fixture
def selector(qtbot) -> FramesSelector:
    """A selector on frames 9 to 19, which the user sees as 10 to 20."""
    widget = FramesSelector.from_frames(9, 19)
    qtbot.addWidget(widget)
    return widget


def record(signal) -> list:
    """Collect what `signal` emits, in order."""
    emitted: list = []
    signal.connect(emitted.append)
    return emitted


def test_spinboxes_count_the_frames_from_one(selector):
    assert selector._start_frame.value() == 10
    assert selector._end_frame.value() == 20


def test_spinboxes_cannot_leave_the_frame_range(selector):
    for spin in (selector._start_frame, selector._end_frame):
        assert (spin.minimum(), spin.maximum()) == (10, 20)

    selector._start_frame.setValue(5)
    selector._end_frame.setValue(99)

    assert selector._start_frame.value() == 10
    assert selector._end_frame.value() == 20


def test_labels_tell_which_spinbox_is_which(selector):
    labels = [label.text() for label in selector.findChildren(QLabel)]

    assert labels == [
        texts.START_FRAME_LABEL,
        texts.END_FRAME_LABEL,
    ]


def test_selector_is_enabled_when_there_are_frames(selector):
    assert selector._start_frame.isEnabled()
    assert selector._end_frame.isEnabled()


def test_changing_start_does_not_announce_frames(selector):
    selected = record(selector.selected_frames_confirmed)

    selector._start_frame.setValue(15)

    assert selected == []


def test_changing_end_does_not_announce_frames(selector):
    selected = record(selector.selected_frames_confirmed)

    selector._end_frame.setValue(17)

    assert selected == []


def test_confirming_start_announces_frames(selector):
    selected = record(selector.selected_frames_confirmed)

    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    assert selected == [FrameRange(14, 19)]


def test_confirming_end_announces_frames(selector):
    selected = record(selector.selected_frames_confirmed)

    selector._end_frame.setValue(17)
    selector._end_frame.editingFinished.emit()

    assert selected == [FrameRange(9, 16)]


def test_confirming_start_uses_with_start_clamping(selector: FramesSelector):
    selector._end_frame.setValue(12)
    selector._end_frame.editingFinished.emit()

    emitted = record(selector.selected_frames_confirmed)

    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    expected = FrameRange(9, 11).with_start(14)

    assert selector.selected_frames == expected
    assert emitted == [expected]
    assert selector._start_frame.value() == expected.start_display
    assert selector._end_frame.value() == expected.end_display


def test_confirming_end_uses_with_end_clamping(selector: FramesSelector):
    selector._start_frame.setValue(18)
    selector._start_frame.editingFinished.emit()

    emitted = record(selector.selected_frames_confirmed)

    selector._end_frame.setValue(14)
    selector._end_frame.editingFinished.emit()

    expected = FrameRange(17, 19).with_end(13)

    assert selector.selected_frames == expected
    assert emitted == [expected]
    assert selector._start_frame.value() == expected.start_display
    assert selector._end_frame.value() == expected.end_display


def test_confirming_single_frame(selector: FramesSelector):
    emitted = record(selector.selected_frames_confirmed)

    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    selector._end_frame.setValue(15)
    selector._end_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(14, 14)
    assert emitted[-1] == FrameRange(14, 14)


def test_bounds_change_does_not_reset_selection_on_confirm(selector: FramesSelector):
    selector.set_frame_range(FrameRange(9, 19), True)

    # The user raises the start of the selection.
    selector._start_frame.setValue(12)
    selector._start_frame.editingFinished.emit()
    assert selector.selected_frames == FrameRange(11, 19)

    # The bounds widen from outside (e.g. the ROI start is lowered).
    selector.set_frame_range(FrameRange(6, 19), False)
    assert selector.selected_frames == FrameRange(11, 19)

    # Lowering the end must not touch the start.
    selector._end_frame.setValue(17)
    selector._end_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(11, 16)
    assert selector._start_frame.value() == 12
    assert selector._frame_range == FrameRange(6, 19)  # bounds untouched


def test_confirming_does_not_emit_twice(
    selector: FramesSelector,
):
    emitted = record(selector.selected_frames_confirmed)

    selector._start_frame.setValue(12)
    selector._start_frame.editingFinished.emit()

    assert len(emitted) == 1


def test_set_frame_range_updates_limits(selector: FramesSelector):
    selector.set_frame_range(FrameRange(19, 29), adjust_frames=True)

    assert selector._start_frame.minimum() == 20
    assert selector._start_frame.maximum() == 30
    assert selector._end_frame.minimum() == 20
    assert selector._end_frame.maximum() == 30


def test_set_frame_range_adjusts_values(selector: FramesSelector):
    selector.set_frame_range(FrameRange(19, 29), adjust_frames=True)

    assert selector._start_frame.value() == 20
    assert selector._end_frame.value() == 30


def test_set_frame_range_preserves_values_without_adjustment(
    selector: FramesSelector,
):
    selector._start_frame.setValue(12)
    selector._start_frame.editingFinished.emit()
    selector._end_frame.setValue(18)
    selector._end_frame.editingFinished.emit()

    selector.set_frame_range(FrameRange(9, 19))

    assert selector._start_frame.value() == 12
    assert selector._end_frame.value() == 18


def test_set_frame_range_none_disables_spinboxes(
    selector: FramesSelector,
):
    emitted = record(selector.selected_frames_confirmed)

    selector.set_frame_range(None)

    assert not selector._start_frame.isEnabled()
    assert not selector._end_frame.isEnabled()
    assert selector._start_frame.value() == 0
    assert selector._end_frame.value() == 0
    assert emitted == [None]


def test_set_frame_range_none_displays_special_value(
    selector: FramesSelector,
):
    selector.set_frame_range(None)

    assert selector._start_frame.specialValueText() == "—"
    assert selector._end_frame.specialValueText() == "—"


def test_restoring_frame_range_enables_spinboxes(
    selector: FramesSelector,
):
    selector.set_frame_range(None)
    selector.set_frame_range(FrameRange(9, 19), adjust_frames=True)

    assert selector._start_frame.isEnabled()
    assert selector._end_frame.isEnabled()
    assert selector._start_frame.value() == 10
    assert selector._end_frame.value() == 20


def test_disabling_preserves_selected_range(
    selector: FramesSelector,
):
    selector._start_frame.setValue(12)
    selector._start_frame.editingFinished.emit()

    selected_range = selector._frame_range

    selector.disable()

    assert not selector._start_frame.isEnabled()
    assert not selector._end_frame.isEnabled()
    assert selector._frame_range == selected_range


def test_enabling_restores_spinboxes(
    selector: FramesSelector,
):
    selector.disable()
    selector.disable(False)

    assert selector._start_frame.isEnabled()
    assert selector._end_frame.isEnabled()


def test_disable_does_not_clear_special_value(
    selector: FramesSelector,
):
    selector.set_frame_range(None)
    selector.disable()

    assert selector._start_frame.specialValueText() == "—"
    assert selector._end_frame.specialValueText() == "—"


def test_disabling_does_not_emit_selection(
    selector: FramesSelector,
):
    emitted = record(selector.selected_frames_confirmed)

    selector.disable()

    assert emitted == []


def test_selected_frames_returns_initial_selection(selector: FramesSelector):
    assert selector.selected_frames == FrameRange(9, 19)


def test_selected_frames_reflects_start_spinbox_value(selector: FramesSelector):
    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(14, 19)


def test_selected_frames_reflects_end_spinbox_value(selector: FramesSelector):
    selector._end_frame.setValue(17)
    selector._end_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(9, 16)


def test_selected_frames_reflects_both_spinbox_values(selector: FramesSelector):
    selector._start_frame.setValue(12)
    selector._start_frame.editingFinished.emit()
    selector._end_frame.setValue(18)
    selector._end_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(11, 17)


def test_selected_frames_reflects_values_after_confirmation(
    selector: FramesSelector,
):
    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(14, 19)


def test_selected_frames_returns_single_frame(selector: FramesSelector):
    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()
    selector._end_frame.setValue(15)
    selector._end_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(14, 14)


def test_selected_frames_returns_none_without_available_frames(
    selector: FramesSelector,
):
    selector.set_frame_range(None)

    assert selector.selected_frames is None


@pytest.mark.parametrize(
    ("selection", "bounds", "expected"),
    [
        # The new bounds cut the start of the selection.
        ((11, 16), (13, 19), (13, 16)),
        # The new bounds cut the end of the selection.
        ((11, 16), (9, 14), (11, 14)),
        # The new bounds cut both ends.
        ((11, 16), (13, 14), (13, 14)),
        # The selection is entirely before the new bounds.
        ((11, 13), (15, 19), (15, 15)),
        # The selection is entirely after the new bounds.
        ((16, 19), (9, 12), (12, 12)),
    ],
)
def test_set_frame_range_clamps_selection_outside_bounds(
    selector: FramesSelector,
    selection: tuple[int, int],
    bounds: tuple[int, int],
    expected: tuple[int, int],
):
    selector._start_frame.setValue(selection[0] + 1)
    selector._start_frame.editingFinished.emit()
    selector._end_frame.setValue(selection[1] + 1)
    selector._end_frame.editingFinished.emit()

    selector.set_frame_range(FrameRange(*bounds))

    assert selector.selected_frames == FrameRange(*expected)
    assert selector._start_frame.value() == expected[0] + 1
    assert selector._end_frame.value() == expected[1] + 1


def test_set_selected_frames_sets_both_ends(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    assert selector.selected_frames == FrameRange(11, 17)
    assert selector._start_frame.value() == 12
    assert selector._end_frame.value() == 18


def test_set_selected_frames_converts_to_zero_based(selector: FramesSelector):
    selector.set_selected_frames(11, 11)

    assert selector.selected_frames == FrameRange(10, 10)


def test_set_selected_frames_only_start_keeps_the_end(selector: FramesSelector):
    selector.set_selected_frames(start=15)

    assert selector.selected_frames == FrameRange(14, 19)
    assert selector._end_frame.value() == 20


def test_set_selected_frames_only_end_keeps_the_start(selector: FramesSelector):
    selector.set_selected_frames(end=17)

    assert selector.selected_frames == FrameRange(9, 16)
    assert selector._start_frame.value() == 10


def test_set_selected_frames_without_values_keeps_the_selection(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    selector.set_selected_frames()

    assert selector.selected_frames == FrameRange(11, 17)


def test_set_selected_frames_announces_the_selection_once(selector: FramesSelector):
    emitted = record(selector.selected_frames_confirmed)

    selector.set_selected_frames(12, 18)

    assert emitted == [FrameRange(11, 17)]


def test_set_selected_frames_single_frame(selector: FramesSelector):
    selector.set_selected_frames(15, 15)

    assert selector.selected_frames == FrameRange(14, 14)
    assert selector._start_frame.value() == 15
    assert selector._end_frame.value() == 15


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (5, 18, (9, 17)),  # start below the bounds
        (12, 99, (11, 19)),  # end above the bounds
        (0, 99, (9, 19)),  # both outside, on opposite sides
        (-3, 18, (9, 17)),  # negative start
        (99, 99, (19, 19)),  # entirely above the bounds
        (3, 3, (9, 9)),  # entirely below the bounds
    ],
)
def test_set_selected_frames_clamps_to_the_bounds(
    selector: FramesSelector,
    start: int,
    end: int,
    expected: tuple[int, int],
):
    selector.set_selected_frames(start, end)

    assert selector.selected_frames == FrameRange(*expected)
    assert selector._start_frame.value() == expected[0] + 1
    assert selector._end_frame.value() == expected[1] + 1


def test_set_selected_frames_start_above_end_collapses_on_the_end(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    selector.set_selected_frames(start=20)

    assert selector.selected_frames == FrameRange(17, 17)


def test_set_selected_frames_end_below_start_collapses_on_the_start(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    selector.set_selected_frames(end=10)

    assert selector.selected_frames == FrameRange(11, 11)


def test_set_selected_frames_does_not_change_the_bounds(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    assert selector._frame_range == FrameRange(9, 19)
    assert (selector._start_frame.minimum(), selector._start_frame.maximum()) == (10, 20)
    assert (selector._end_frame.minimum(), selector._end_frame.maximum()) == (10, 20)


def test_set_selected_frames_is_used_by_next_confirmation(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    # Lowering the end must start from the programmatic selection, not from the full range.
    selector._end_frame.setValue(16)
    selector._end_frame.editingFinished.emit()

    assert selector.selected_frames == FrameRange(11, 15)


def test_set_selected_frames_survives_a_bounds_change(selector: FramesSelector):
    selector.set_selected_frames(12, 18)

    selector.set_frame_range(FrameRange(6, 25))

    assert selector.selected_frames == FrameRange(11, 17)


def test_set_selected_frames_without_frames_does_nothing(selector: FramesSelector):
    selector.set_frame_range(None)
    emitted = record(selector.selected_frames_confirmed)

    selector.set_selected_frames(12, 18)

    assert selector.selected_frames is None
    assert selector._start_frame.value() == 0
    assert selector._end_frame.value() == 0
    assert emitted == []
