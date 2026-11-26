from pathlib import Path
from typing import override

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDragLeaveEvent, QDragMoveEvent, QDropEvent
from PySide6.QtWidgets import QLabel

from apkit4d.gui.constants import names, texts


class FileDropSurface(QLabel):
    """A drag-and-drop surface used to load a file into the app."""

    file_dropped = Signal(Path)

    def __init__(self) -> None:
        super().__init__(texts.PLACEHOLDER)
        self.setObjectName(names.CENTER_PLACEHOLDER)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setWordWrap(True)
        self.setAcceptDrops(True)
        self.setProperty("dragActive", False)

    @override
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        self._handle_drag_event(event)

    @override
    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        self._handle_drag_event(event)

    @override
    def dragLeaveEvent(self, event: QDragLeaveEvent) -> None:
        self._set_drag_active(False)
        event.accept()

    @override
    def dropEvent(self, event: QDropEvent) -> None:
        path = self._first_local_path(event.mimeData())
        self._set_drag_active(False)
        if path is None:
            event.ignore()
            return
        self.file_dropped.emit(path)
        event.acceptProposedAction()

    @staticmethod
    def _first_local_path(mime_data: QMimeData) -> Path | None:
        for url in mime_data.urls():
            if url.isLocalFile():
                return Path(url.toLocalFile())
        return None

    def _handle_drag_event(self, event: QDragEnterEvent | QDragMoveEvent) -> None:
        drag_active = self._first_local_path(event.mimeData()) is not None
        self._set_drag_active(drag_active)
        if drag_active:
            event.acceptProposedAction()
        else:
            event.ignore()

    def _set_drag_active(self, active: bool) -> None:
        if self.property("dragActive") == active:
            return
        self.setProperty("dragActive", active)
        self.style().unpolish(self)
        self.style().polish(self)
        self.update()
