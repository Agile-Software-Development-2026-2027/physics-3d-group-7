from PySide6.QtWidgets import QWidget


def find_widget(parent: QWidget, widget_type: type, name: str):
    widget = parent.findChild(widget_type, name)
    assert widget is not None, f"Widget '{name}' of type {widget_type.__name__} not found in {parent}"
    return widget


def painted_color(widget: QWidget, x: int, y: int) -> str:
    """Hex color that `widget` paints at the point (x, y), with its stylesheet."""
    return widget.grab().toImage().pixelColor(x, y).name()
