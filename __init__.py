from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import *
from anki.notes import Note
from . import AnkiExamCard
from .shared import questions_cycle




#Main selection window to all for various AnkiExam tools
# ...existing imports...

DEBUG = False
#initialize uploaded pdf content
uploaded_txt_content = {"content": ""}

questions_cycle = {
    "questions": [],
    "index": 0
}

from PyQt6.QtCore import QThread, pyqtSignal


#Worker thread to handle question generation
class AnswerWorker(QThread):
    finished = pyqtSignal(str, int)
    error = pyqtSignal(str)
    def __init__(self, user_answer, question):
        super().__init__()
        self.user_answer = user_answer
        self.question = question
    def run(self):
        try:
            from .main import together_api_input
            output, total_tokens = together_api_input(self.user_answer, self.question)
            self.finished.emit(output, total_tokens)
        except Exception as e:
            self.error.emit(str(e))


# Helper to create a styled, centered button
def make_button(text, on_click):
    btn = QPushButton(text)
    btn.setFixedWidth(180)
    btn.setFixedHeight(36)
    btn.setStyleSheet("font-weight: bold; color: white; background-color: #ff455b; border-radius: 4px; font-size: 14px;")
    btn.clicked.connect(on_click)
    btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    btn_container = QWidget()
    btn_layout = QHBoxLayout()
    btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
    btn_layout.addWidget(btn)
    btn_layout.setContentsMargins(0, 8, 0, 8)
    btn_container.setLayout(btn_layout)
    return btn_container

#Main selection window to all for various AnkiExam tools
def selection_window_gui():
    #from .pdf_training import uploaded_txt_content #import cached uploaded content
    dlg = QDialog(mw)
    dlg.setWindowTitle("AnkiExam Tool Selection")
    dlg.setStyleSheet("background-color: #ff91da; color: white; font-weight: bold; font-size: 16px;")
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    label = QLabel("Welcome to the AnkiExam Tool Selection!\n\n"
                   "Please select a tool from the menu bar.\n\n")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    # If a TXT file is in cache, show a box
    if uploaded_txt_content.get("content"):
        cache_label = QLabel("PDF File in Cache")
        cache_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cache_label.setStyleSheet("background: #fff3cd; color: #856404; border: 1px solid #ffeeba; border-radius: 4px; padding: 8px; font-size: 14px;")
        layout.addWidget(cache_label)

    if questions_cycle.get("questions"):
        # If questions are in cache, show a box
        cache_label = QPushButton("Questions are in Cache")
        cache_label.setStyleSheet("background: #fff3cd; color: #856404; border: 1px solid #ffeeba; border-radius: 4px; padding: 8px; font-size: 14px;")
        #layout.addWidget(cache_label)
        layout.addWidget(make_button("Inspect Cache", inspect_cache))


    # Button 1: Input Training Data
    def on_training():
        dlg.accept()
        from .pdf_training import show_txt_training_gui
        show_txt_training_gui()
    layout.addWidget(make_button("Input Training Data", on_training))

    # Button 2: Input Question
    def on_question():
        dlg.accept()
        show_custom_gui()
    layout.addWidget(make_button("Input Question", on_question))

    # Close button
    def on_close():
        dlg.accept()
    layout.addWidget(make_button("Close", on_close))

    dlg.setLayout(layout)
    dlg.setMinimumWidth(400)
    dlg.setMinimumHeight(300)
    dlg.exec()
    
# Function to inspect the cache of questions

def inspect_cache():
    dlg = QDialog(mw)
    dlg.setWindowTitle("Cache Inspection")
    from .pdf_training import questions_cycle  # Ensure you use the shared dict
    questions = questions_cycle["questions"]
    showInfo(f"Questions: {(questions)}")
    if not questions:
        showInfo("No questions in cache!")
        return
    dlg.setMinimumWidth(800)
    dlg.setMinimumHeight(200)
    dlg.setStyleSheet("background-color: #ff91da; color: white; font-weight: bold; font-size: 16px;")
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    layout.addWidget(make_button("Close", dlg.accept))
    dlg.setLayout(layout)
    dlg.exec()

#Here is eventually where i will feed through the question from the training data:
#DYNAMIC_STRING = "This is a dynamic string. Change me as needed!"
QuestionToAsk = "What is the capital of Canada?"
#DYNAMIC_STRING = "What is the capital of Canada?"

#a new custom gui funciton
def show_custom_gui():
    from .pdf_training import questions_cycle  # Ensure you use the shared dict
    #import that is imported from pdf_training.py

    questions = questions_cycle["questions"]
    idx = questions_cycle["index"]
    #showInfo(f"Current question index: {idx}, Total questions: {len(questions)}")

    if not questions or idx >= len(questions):
        showInfo("No more questions!")
        return

    QuestionToAsk = questions[idx]

    dlg = QDialog(mw)
    dlg.setWindowTitle("AnkiExam Tool")
    dlg.setMinimumWidth(800)
    dlg.setMinimumHeight(200)
    dlg.setStyleSheet("background-color: #ff91da; color: white; font-weight: bold; font-size: 16px;")
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    label = QLabel("Please enter your answer to the question below.\n\n")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    # Dynamic string label
    dynamic_label = QLabel(QuestionToAsk)
    dynamic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dynamic_label.setStyleSheet("font-size: 13px; color: #222; background: transparent;")
    layout.addWidget(dynamic_label)

    input_field = QLineEdit()
    input_field.setPlaceholderText("Type your answer here...")
    input_field.setFixedHeight(36)
    input_field.setStyleSheet("font-weight: bold; color: black; background-color: gray; border-radius: 4px; font-size: 12px;")
    layout.addWidget(input_field)

    btn = QPushButton("OK")
    layout.addWidget(btn)
    dlg.setLayout(layout)

    # Center the dialog on the screen
    dlg.show()
    qr = dlg.frameGeometry()
    cp = dlg.screen().availableGeometry().center()
    qr.moveCenter(cp)
    dlg.move(qr.topLeft())

    def on_accept():
        user_answer_input_field = input_field.text()
        if not user_answer_input_field.strip():
            showInfo("Please enter an answer.")
            return

        btn.setEnabled(False)

        # Show loading dialog
        loading_dialog = QDialog(dlg)
        loading_dialog.setWindowTitle("Answer Loading...")
        loading_layout = QVBoxLayout()
        loading_label = QLabel("Checking your answer, please wait...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)
        loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)  # Modal to dlg
        loading_dialog.raise_()
        loading_dialog.activateWindow()

        progress = QProgressBar()
        progress.setRange(0, 0)
        loading_layout.addWidget(progress)
        loading_dialog.setLayout(loading_layout)
        loading_dialog.setMinimumWidth(400)
        loading_dialog.setMinimumHeight(120)
        loading_dialog.show()
        QApplication.processEvents()

        # Start answer worker
        worker = AnswerWorker(user_answer_input_field, QuestionToAsk)
        dlg.worker = worker  # Prevent GC

        def on_finished(output, total_tokens):
            loading_dialog.close()
            #can also switcht to the dlg window if you want to keep the style
            popup = QDialog(mw)
            popup.setWindowTitle("API Output")
            popup_layout = QVBoxLayout()
            popup_label = QLabel(f"User's Answer: {user_answer_input_field}, \n\nOutput:\n{output}, \n\nTotal Tokens: {total_tokens}")
            popup_label.setWordWrap(True)
            popup_label.setStyleSheet("font-size: 14px;")
            popup_layout.addWidget(popup_label)
            popup.setLayout(popup_layout)
            popup.exec()
            dlg.accept()
            questions_cycle["index"] += 1
            if questions_cycle["index"] < len(questions_cycle["questions"]):
                show_custom_gui()
            else:
                showInfo("You have completed all questions!")
            dlg.worker = None

        def on_error(error_msg):
            loading_dialog.close()
            showInfo(f"API Error: {error_msg}")
            btn.setEnabled(True)
            dlg.worker = None

        worker.finished.connect(on_finished)
        worker.error.connect(on_error)
        worker.start()

    btn.clicked.connect(on_accept)
    dlg.exec()


#show automatically for testing...
if DEBUG:
    show_custom_gui()
else:
    print(f"DEBUG mode disabled.")


# Add menu entry under Tools
action = QAction("AnkiExam Tool", mw)
#qconnect(action.triggered, show_custom_gui)
qconnect(action.triggered, selection_window_gui)
#action.triggered.connect(show_custom_gui)
mw.form.menuTools.addAction(action)




