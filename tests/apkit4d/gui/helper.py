from PySide6.QtWidgets import QWidget


def find_widget(parent: QWidget, widget_type: type, name: str):
    widget = parent.findChild(widget_type, name)
    assert widget is not None, f"Widget '{name}' of type {widget_type.__name__} not found in {parent}"
    return widget
