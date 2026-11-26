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


def test_confirming_start_uses_with_start_clamping(
    selector: FramesSelector,
):
    # First confirm the end frame.
    selector._end_frame.setValue(12)
    selector._end_frame.editingFinished.emit()

    emitted = record(selector.selected_frames_confirmed)

    # Then move the start beyond the confirmed end.
    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    expected = FrameRange(9, 11).with_start(14)

    assert selector._frame_range == expected
    assert emitted == [expected]
    assert selector._start_frame.value() == expected.start_display
    assert selector._end_frame.value() == expected.end_display


def test_confirming_end_uses_with_end_clamping(
    selector: FramesSelector,
):
    # First confirm the start frame.
    selector._start_frame.setValue(18)
    selector._start_frame.editingFinished.emit()

    emitted = record(selector.selected_frames_confirmed)

    # Then move the end before the confirmed start.
    selector._end_frame.setValue(14)
    selector._end_frame.editingFinished.emit()

    expected = FrameRange(17, 19).with_end(13)

    assert selector._frame_range == expected
    assert emitted == [expected]
    assert selector._start_frame.value() == expected.start_display
    assert selector._end_frame.value() == expected.end_display


def test_confirming_single_frame(selector: FramesSelector):
    emitted = record(selector.selected_frames_confirmed)

    selector._start_frame.setValue(15)
    selector._start_frame.editingFinished.emit()

    selector._end_frame.setValue(15)
    selector._end_frame.editingFinished.emit()

    assert selector._frame_range == FrameRange(14, 14)
    assert emitted[-1] == FrameRange(14, 14)


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
    selector._end_frame.setValue(18)

    selector.set_frame_range(FrameRange(9, 19))

    assert selector._start_frame.value() == 12
    assert selector._end_frame.value() == 18


def test_set_frame_range_emits_current_selection(
    selector: FramesSelector,
):
    emitted = record(selector.selected_frames_confirmed)

    selector.set_frame_range(FrameRange(9, 19), adjust_frames=True)

    assert emitted == [FrameRange(9, 19)]


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
