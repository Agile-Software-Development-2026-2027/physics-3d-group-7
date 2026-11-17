"""
Unit tests for FrameSlider.
"""

from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QImage, QMouseEvent
from PySide6.QtWidgets import QApplication

from apkit4d.gui.constants import appearance
from apkit4d.gui.views.widgets.frame_slider import FrameSlider


def make_slider(qtbot, **options) -> FrameSlider:
    slider = FrameSlider(**options)
    qtbot.addWidget(slider)
    slider.setRange(0, 99)
    slider.resize(200, slider.height())
    return slider


def look_before_and_while_hovering(slider: FrameSlider) -> tuple[QImage, QImage]:
    """Images of the slider before and while the mouse is over the middle of its groove."""
    before = slider.grab().toImage()
    middle = QPointF(slider.width() / 2, slider.height() - appearance.SLIDER_HEIGHT / 2)
    move = QMouseEvent(
        QEvent.Type.MouseMove,
        middle,
        slider.mapToGlobal(middle),
        Qt.MouseButton.NoButton,
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
    )
    QApplication.sendEvent(slider, move)
    return before, slider.grab().toImage()


def test_preview_follows_the_mouse(qtbot) -> None:
    slider = make_slider(qtbot)

    before, hovering = look_before_and_while_hovering(slider)

    assert slider.height() == appearance.SLIDER_HEADROOM + appearance.SLIDER_HEIGHT
    assert hovering != before


def test_without_preview_the_slider_keeps_no_room_and_ignores_the_mouse(qtbot) -> None:
    slider = make_slider(qtbot, preview=False)

    before, hovering = look_before_and_while_hovering(slider)

    assert slider.height() == appearance.SLIDER_HEIGHT
    assert hovering == before
