from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget


def labeled_row(
    label_text: str, widget: QWidget, name: str | None = None, tooltip: str | None = None
) -> QWidget:
    """Creates a new widget consisting of row split in two, with on the left a label
    on the right any widget.

    Args:
        label_text (str): the label to display on the left
        widget (QWidget): any widget to put on the right
        tooltip (str | None): an optional tooltip for the whole row

    Returns:
        The new widget row.
    """

    row = QWidget()
    if tooltip:
        row.setToolTip(tooltip)
    if name:
        row.setObjectName(name)
    layout = QHBoxLayout(row)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(5)
    layout.addWidget(QLabel(label_text))  # stretch=1
    layout.addWidget(widget)  # stretch=1
    return row
