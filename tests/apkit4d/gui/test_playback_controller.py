import pytest

from apkit4d.core.frame_range import FrameRange
from apkit4d.gui.constants import playback
from apkit4d.gui.controllers.playback_controller import PlaybackController
from apkit4d.gui.views.playback.playback_bar import PlaybackBar


@pytest.fixture
def bar(qtbot) -> PlaybackBar:
    widget = PlaybackBar()
    qtbot.addWidget(widget)
    return widget


@pytest.fixture
def playback_controller(bar) -> PlaybackController:
    controller = PlaybackController(bar)
    controller.set_frame_count(20)
    return controller


def test_every_frame_can_be_reached_until_a_range_is_set(playback_controller) -> None:
    playback_controller.go_to_frame(0)
    assert playback_controller.frame == 0

    playback_controller.go_to_frame(100)
    assert playback_controller.frame == 19


def test_range_limits_requests_to_its_ends(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(5, 10))

    playback_controller.go_to_frame(0)
    assert playback_controller.frame == 5

    playback_controller.go_to_frame(19)
    assert playback_controller.frame == 10

    playback_controller.go_to_frame(8)
    assert playback_controller.frame == 8


def test_range_limits_next_and_previous(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(5, 10))
    playback_controller.go_to_frame(5)

    playback_controller.previous_frame()
    assert playback_controller.frame == 5

    playback_controller.set_step(4)
    playback_controller.next_frame()
    assert playback_controller.frame == 9
    playback_controller.next_frame()
    # 9 + 4 is past the end, so it stays on the last frame of the range
    assert playback_controller.frame == 10
    playback_controller.next_frame()
    assert playback_controller.frame == 10


def test_current_frame_outside_the_new_range_moves_inside_and_is_announced(
    playback_controller, qtbot
) -> None:
    playback_controller.go_to_frame(15)

    with qtbot.waitSignal(playback_controller.frame_changed) as moved:
        playback_controller.set_frame_range(FrameRange(2, 8))

    assert moved.args == [8]
    assert playback_controller.frame == 8


def test_current_frame_before_the_new_range_moves_to_its_start(playback_controller, qtbot) -> None:
    playback_controller.go_to_frame(1)

    with qtbot.waitSignal(playback_controller.frame_changed) as moved:
        playback_controller.set_frame_range(FrameRange(6, 12))

    assert moved.args == [6]


def test_current_frame_inside_the_new_range_does_not_move(playback_controller, qtbot) -> None:
    playback_controller.go_to_frame(7)

    with qtbot.assertNotEmitted(playback_controller.frame_changed):
        playback_controller.set_frame_range(FrameRange(2, 12))

    assert playback_controller.frame == 7


def test_slider_handle_is_brought_inside_the_new_range(playback_controller, bar) -> None:
    playback_controller.go_to_frame(15)

    playback_controller.set_frame_range(FrameRange(2, 8))

    assert bar._slider.value() == 8


def test_slider_handle_cannot_be_dragged_out_of_the_range(playback_controller, bar) -> None:
    playback_controller.set_frame_range(FrameRange(2, 5))
    playback_controller.go_to_frame(5)

    bar._slider.setValue(8)  # the user drags the handle past the end of the range
    assert (playback_controller.frame, bar._slider.value()) == (5, 5)

    bar._slider.setValue(0)
    assert (playback_controller.frame, bar._slider.value()) == (2, 2)


def test_no_range_makes_every_frame_reachable_again(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(5, 10))

    playback_controller.set_frame_range(None)
    playback_controller.go_to_frame(0)
    assert playback_controller.frame == 0

    playback_controller.go_to_frame(100)
    assert playback_controller.frame == 19


def test_range_beyond_the_recording_stops_at_its_last_frame(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(5, 100))

    playback_controller.go_to_frame(100)

    assert playback_controller.frame == 19


def test_step_cannot_exceed_the_frames_of_the_range(playback_controller, bar) -> None:
    playback_controller.set_step(10)

    playback_controller.set_frame_range(FrameRange(5, 8))

    assert playback_controller.step == 3  # at most one less than the frames of the range
    assert bar._step.value() == 3


def test_step_can_grow_again_when_the_range_does(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(5, 8))
    playback_controller.set_step(10)
    assert playback_controller.step == 3

    playback_controller.set_frame_range(None)
    playback_controller.set_step(10)

    assert playback_controller.step == 10


def test_playing_starts_from_the_first_frame_of_the_range(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(5, 10))
    playback_controller.go_to_frame(10)

    playback_controller.set_playing(True)

    assert playback_controller.is_playing
    assert playback_controller.frame == 5
    playback_controller.set_playing(False)


def test_playing_stops_at_the_last_frame_of_the_range(playback_controller, qtbot) -> None:
    playback_controller.set_frame_range(FrameRange(5, 7))
    playback_controller.go_to_frame(5)
    playback_controller.set_speed(playback.MAX_SPEED_FPS)

    playback_controller.set_playing(True)
    qtbot.waitUntil(lambda: not playback_controller.is_playing, timeout=5000)

    assert playback_controller.frame == 7


def test_range_of_one_frame_has_nothing_to_play(playback_controller) -> None:
    playback_controller.set_frame_range(FrameRange(7, 7))

    playback_controller.set_playing(True)

    assert not playback_controller.is_playing
    assert playback_controller.frame == 7


def test_playing_stops_when_the_range_shrinks_to_one_frame(playback_controller) -> None:
    playback_controller.set_playing(True)
    assert playback_controller.is_playing

    playback_controller.set_frame_range(FrameRange(7, 7))

    assert not playback_controller.is_playing


def test_playing_goes_on_when_the_range_still_has_frames(playback_controller) -> None:
    playback_controller.set_playing(True)

    playback_controller.set_frame_range(FrameRange(7, 12))

    assert playback_controller.is_playing
    playback_controller.set_playing(False)


def test_the_slider_marks_the_range(playback_controller, bar) -> None:
    playback_controller.set_frame_range(FrameRange(5, 10))
    assert bar._slider._marked_range == (5, 10)

    playback_controller.set_frame_range(None)
    assert bar._slider._marked_range is None
