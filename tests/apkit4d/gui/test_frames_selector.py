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

    assert labels == [texts.START_FRAME_LABEL, texts.END_FRAME_LABEL]


def test_selector_is_enabled_when_there_are_frames(selector):
    assert selector._start_frame.isEnabled()
    assert selector._end_frame.isEnabled()


def test_changing_the_start_announces_the_frames_from_zero(selector):
    selected = record(selector.selected_frames_changed)

    selector._start_frame.setValue(15)

    assert selected == [FrameRange(14, 19)]


def test_changing_the_end_announces_the_frames_from_zero(selector):
    selected = record(selector.selected_frames_changed)

    selector._end_frame.setValue(17)

    assert selected == [FrameRange(9, 16)]


def test_start_past_the_end_pushes_the_end_and_announces_once(selector):
    selector._end_frame.setValue(12)
    selected = record(selector.selected_frames_changed)

    selector._start_frame.setValue(15)

    assert (selector._start_frame.value(), selector._end_frame.value()) == (15, 15)
    assert selected == [FrameRange(14, 14)]


def test_end_before_the_start_pulls_the_start_and_announces_once(selector):
    selector._start_frame.setValue(18)
    selected = record(selector.selected_frames_changed)

    selector._end_frame.setValue(14)

    assert (selector._start_frame.value(), selector._end_frame.value()) == (14, 14)
    assert selected == [FrameRange(13, 13)]


def test_selecting_a_single_frame_is_allowed(selector):
    selected = record(selector.selected_frames_changed)

    selector._end_frame.setValue(10)

    assert selected == [FrameRange(9, 9)]
    assert selected[0].count == 1


def test_new_range_moves_the_limits_and_keeps_the_choice_inside_them(selector):
    selector._start_frame.setValue(13)
    selector._end_frame.setValue(16)

    selector.set_frame_range(FrameRange(0, 29))

    for spin in (selector._start_frame, selector._end_frame):
        assert (spin.minimum(), spin.maximum()) == (1, 30)
    assert (selector._start_frame.value(), selector._end_frame.value()) == (13, 16)


def test_new_range_can_select_all_its_frames(selector):
    selected = record(selector.selected_frames_changed)

    selector.set_frame_range(FrameRange(0, 29), True)

    assert (selector._start_frame.value(), selector._end_frame.value()) == (1, 30)
    assert selected[-1] == FrameRange(0, 29)


def test_shorter_range_pulls_the_choice_inside_it(selector):
    selector.set_frame_range(FrameRange(0, 4))

    assert selector._start_frame.value() == 5
    assert selector._end_frame.value() == 5


def test_new_range_is_announced(selector):
    ranges = record(selector.frame_range_changed)

    selector.set_frame_range(FrameRange(0, 29))

    assert ranges == [FrameRange(0, 29)]


def test_no_range_disables_the_spinboxes_and_shows_a_dash(selector):
    selector.set_frame_range(None)

    for spin in (selector._start_frame, selector._end_frame):
        assert not spin.isEnabled()
        assert spin.specialValueText() == "—"
        assert (spin.minimum(), spin.maximum(), spin.value()) == (0, 0, 0)


def test_no_range_announces_no_frames(selector):
    selected = record(selector.selected_frames_changed)
    ranges = record(selector.frame_range_changed)

    selector.set_frame_range(None)

    assert selected == [None]
    assert ranges == [None]


def test_a_range_after_no_range_enables_the_spinboxes_again(selector):
    selector.set_frame_range(None)

    selector.set_frame_range(FrameRange(0, 9), True)

    for spin in (selector._start_frame, selector._end_frame):
        assert spin.isEnabled()
        assert spin.specialValueText() == ""
    assert (selector._start_frame.value(), selector._end_frame.value()) == (1, 10)


def test_nothing_is_announced_while_there_are_no_frames(selector):
    selector.set_frame_range(None)
    selected = record(selector.selected_frames_changed)

    selector._start_frame.setValue(0)
    selector._end_frame.setValue(0)

    assert selected == []


def test_disable_blocks_the_spinboxes_and_enable_gives_them_back(selector):
    selector.disable(True)
    assert not selector._start_frame.isEnabled()
    assert not selector._end_frame.isEnabled()
    assert selector._start_frame.specialValueText() == "—"

    selector.disable(False)
    assert selector._start_frame.isEnabled()
    assert selector._end_frame.isEnabled()
    assert selector._start_frame.specialValueText() == ""


def test_disable_with_no_frames_stays_disabled_after_enabling(selector):
    selector.set_frame_range(None)

    selector.disable(False)

    assert not selector._start_frame.isEnabled()
    assert not selector._end_frame.isEnabled()


def test_disable_keeps_the_choice(selector):
    selector._start_frame.setValue(13)

    selector.disable(True)
    selector.disable(False)

    assert selector._start_frame.value() == 13
