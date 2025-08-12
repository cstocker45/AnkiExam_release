from aqt.qt import *


class HoverFilter(QObject):
    def __init__(self, on_enter, on_leave, parent=None):
        super().__init__(parent)
        self._enter = on_enter
        self._leave = on_leave

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.Enter:
            self._enter()
            return True
        elif event.type() == QEvent.Type.Leave:
            self._leave()
            return True
        return False

