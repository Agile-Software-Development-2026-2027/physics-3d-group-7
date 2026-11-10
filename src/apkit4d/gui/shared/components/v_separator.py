from PySide6.QtWidgets import QFrame, QWidget


class VSeparator(QFrame):
    """A vertical separator line widget for layout divisions."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)

        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Sunken)
        self.setLineWidth(1)
