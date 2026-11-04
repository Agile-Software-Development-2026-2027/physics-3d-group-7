import sys

from PySide6.QtCore import QEasingCurve, QParallelAnimationGroup, QPropertyAnimation
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class AccordionSection(QWidget):
    def __init__(self, title="", parent=None):
        super().__init__(parent)

        # Primary layouts
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # Header Button (Toggles the collapse)
        self.toggle_button = QPushButton(f"▼ {title}")
        self.toggle_button.setCheckable(True)
        self.toggle_button.setChecked(False)
        self.toggle_button.setStyleSheet("""
            QPushButton {
                background-color: #2b2b2b;
                color: #ffffff;
                border: 1px solid #3f3f3f;
                padding: 10px;
                text-align: left;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #3a3a3a;
            }
            QPushButton:checked {
                background-color: #1e1e1e;
            }
            QPushButton:checked:hover {
                background-color: #3a3a3a;
            }
        """)

        # Content Container
        self.content_area = QFrame()
        self.content_layout = QVBoxLayout(self.content_area)
        self.content_layout.setContentsMargins(10, 10, 10, 10)
        self.content_area.setStyleSheet("""
            QFrame {
                background-color: #202020;
                border: 1px solid #3f3f3f;
                border-top: none;
            }
        """)

        # Fix height expanding behaviors for animations
        self.content_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.content_area.setMaximumHeight(0)

        # Add to main section layout
        self.main_layout.addWidget(self.toggle_button)
        self.main_layout.addWidget(self.content_area)

        # Smooth (operator) Animation
        self.toggle_animation = QPropertyAnimation(self.content_area, b"maximumHeight")
        self.toggle_animation.setDuration(300)  # milliseconds
        self.toggle_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)

        self.anim_group = QParallelAnimationGroup(self)
        self.anim_group.addAnimation(self.toggle_animation)

        # Connect the click signal
        self.toggle_button.clicked.connect(self.on_toggle)

    def add_widget(self, widget):
        """Helper function to add child widgets inside the accordion content area."""
        self.content_layout.addWidget(widget)

    def on_toggle(self, checked):
        # Update text/arrow indicator
        title_text = self.toggle_button.text()[2:]
        self.toggle_button.setText(f"▲ {title_text}" if checked else f"▼ {title_text}")

        # Calculate start and end heights for the animation
        # Hint: layout().sizeHint() accurately measures the height of everything inside
        content_height = self.content_layout.sizeHint().height() + 20

        start_height = 0 if checked else content_height
        end_height = content_height if checked else 0

        self.toggle_animation.setStartValue(start_height)
        self.toggle_animation.setEndValue(end_height)

        self.anim_group.start()


class AccordionDemo(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 Accordion Layout")
        self.resize(400, 500)
        self.setStyleSheet("background-color: #121212;")

        # Window main layout
        window_layout = QVBoxLayout(self)

        # Scroll area in case content overflows
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)

        scroll_content = QWidget()
        self.accordion_layout = QVBoxLayout(scroll_content)
        self.accordion_layout.setContentsMargins(5, 5, 5, 5)
        self.accordion_layout.setSpacing(5)

        # Sections
        for i in range(1, 10):
            section = AccordionSection(f"Section {i}")
            for j in range(1, 4):
                section.add_widget(QLabel(f"Item {j} in Section {i}"))
            self.accordion_layout.addWidget(section)

        # Add a stretch at the bottom to force items up when collapsed
        self.accordion_layout.addStretch()

        scroll.setWidget(scroll_content)
        window_layout.addWidget(scroll)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    demo = AccordionDemo()
    demo.show()
    sys.exit(app.exec())
