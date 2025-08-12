from aqt.qt import *
import os


class PersistentDialog(QDialog):
    def closeEvent(self, event):
        event.ignore()
        self.hide()


def make_button(text: str, on_click):
    btn = QPushButton(text)
    btn.setFixedWidth(180)
    btn.setFixedHeight(36)
    btn.setStyleSheet(
        "font-weight: bold; color: white; background-color: #ff455b; border-radius: 4px; font-size: 14px;"
    )
    btn.clicked.connect(on_click)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn_container = QWidget()
    btn_layout = QHBoxLayout()
    btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    btn_layout.addWidget(btn)
    btn_layout.setContentsMargins(0, 8, 0, 8)
    btn_container.setLayout(btn_layout)
    return btn_container


def get_icon_path(icon_name: str) -> str:
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons', icon_name)

