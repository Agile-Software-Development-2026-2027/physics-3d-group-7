"""
Unit tests for ColorButton.
"""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QColorDialog

from apkit4d.gui.views.widgets.color_button import ColorButton

TITLE = "Pick a color"


@pytest.fixture
def button(qtbot) -> ColorButton:
    color_button = ColorButton(TITLE)
    qtbot.addWidget(color_button)
    return color_button


def test_color_is_empty_until_it_is_set(button) -> None:
    assert button.color == ""
    assert button.icon().isNull()


def test_set_color_shows_the_hex_code_and_a_square_of_the_color(button) -> None:
    button.set_color("red")

    assert button.color == "#ff0000"
    assert button.text() == "#ff0000"
    square = button.icon().pixmap(button.iconSize()).toImage()
    center = square.pixelColor(square.width() // 2, square.height() // 2)
    assert center == QColor("red")


def test_dialog_starts_from_the_current_color_and_has_the_title(button, qtbot, monkeypatch) -> None:
    calls = []

    def fake_get_color(*args):
        calls.append(args)
        return QColor("#00ff00")

    monkeypatch.setattr(QColorDialog, "getColor", fake_get_color)
    button.set_color("#123456")

    with qtbot.waitSignal(button.color_chosen, timeout=1000) as blocker:
        qtbot.mouseClick(button, Qt.MouseButton.LeftButton)

    initial, _parent, title = calls[0]
    assert initial == QColor("#123456")
    assert title == TITLE
    assert blocker.args == ["#00ff00"]
    assert button.color == "#123456"  # the button waits for set_color to change
