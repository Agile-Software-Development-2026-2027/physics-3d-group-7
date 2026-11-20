"""
Counter that shows the current frame over the total, for example "43 / 300".
"""

from typing import override

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QFont, QFontDatabase, QFontMetrics, QPainter, QPaintEvent, QPalette
from PySide6.QtWidgets import QSizePolicy, QWidget

from apkit4d.gui.constants import appearance, names, texts
from apkit4d.gui.views.widgets.colors import mix

ColorRole = QPalette.ColorRole
ColorGroup = QPalette.ColorGroup


class FrameCounter(QWidget):
    """
    Shows which frame is on screen and how many frames there are.

    The frames are shown from 1, as people count, while the methods use indices from 0. The current frame
    is bold and the total is dimmed. The font has digits of the same width, and the widget is as wide as
    the widest text it can show, so nothing around it moves while the frames go by.

    Args:
        parent: Qt parent.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(names.FRAME_COUNTER)
        font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        font.setPointSizeF(appearance.COUNTER_FONT_POINTS)
        self.setFont(font)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self._frame = 0
        self._count = 0

    @property
    def text(self) -> str:
        """What the counter shows, for example "43 / 300"."""
        return self._current_text() + self._total_text()

    def set_frame(self, frame: int) -> None:
        """
        Show `frame` as the current frame.

        Args:
            frame: Index of the frame, starting from 0.
        """
        self._frame = frame
        self.update()

    def set_frame_count(self, count: int) -> None:
        """
        Show `count` as the total. With 0 the counter shows dashes, because there is nothing to count.

        Args:
            count: Number of frames of the recording.
        """
        self._count = count
        self.updateGeometry()
        self.update()

    @override
    def sizeHint(self) -> QSize:
        metrics = QFontMetrics(self.font())
        digits = str(max(self._count, 1))
        widest = digits + texts.COUNTER_SEPARATOR + digits
        return QSize(
            metrics.horizontalAdvance(widest), metrics.height() + appearance.COUNTER_VERTICAL_PADDING
        )

    @override
    def minimumSizeHint(self) -> QSize:
        return self.sizeHint()

    @override
    def paintEvent(self, _event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        palette = self.palette()
        if self.isEnabled():
            ink = palette.color(ColorRole.WindowText)
            muted = mix(palette.color(ColorRole.Window), ink, appearance.COUNTER_MUTED_MIX)
        else:
            ink = muted = palette.color(ColorGroup.Disabled, ColorRole.WindowText)

        bold = QFont(self.font())
        bold.setWeight(QFont.Weight.DemiBold)
        current = self._current_text()
        area = QRectF(self.rect())
        alignment = Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft

        painter.setFont(bold)
        painter.setPen(ink)
        painter.drawText(area, alignment, current)

        painter.setFont(self.font())
        painter.setPen(muted)
        painter.drawText(
            area.adjusted(QFontMetrics(bold).horizontalAdvance(current), 0, 0, 0),
            alignment,
            self._total_text(),
        )

    def _current_text(self) -> str:
        return str(self._frame + 1) if self._count else texts.COUNTER_EMPTY

    def _total_text(self) -> str:
        return texts.COUNTER_SEPARATOR + (str(self._count) if self._count else texts.COUNTER_EMPTY)
