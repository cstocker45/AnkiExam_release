from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo
try:
    from PyQt6.QtWebEngineWidgets import QWebEngineView
    WEBENGINE_AVAILABLE = True
except ImportError:
    WEBENGINE_AVAILABLE = False

def show_pdf_training_gui():
    dlg = QDialog(mw)
    dlg.setWindowTitle("Upload and View PDF")
    dlg.setMinimumWidth(800)
    dlg.setMinimumHeight(600)
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    label = QLabel("Upload a PDF file to view it below.")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    upload_btn = QPushButton("Upload PDF")
    layout.addWidget(upload_btn)

    if WEBENGINE_AVAILABLE:
        pdf_viewer = QWebEngineView()
        layout.addWidget(pdf_viewer)
    else:
        pdf_viewer = None
        layout.addWidget(QLabel("PDF viewing is not available (PyQt6-WebEngine not installed)."))

    def on_upload():
        file_path, _ = QFileDialog.getOpenFileName(dlg, "Select PDF File", "", "PDF Files (*.pdf)")
        if file_path and pdf_viewer:
            pdf_viewer.load(QUrl.fromLocalFile(file_path))

    upload_btn.clicked.connect(on_upload)

    dlg.setLayout(layout)
    dlg.exec()