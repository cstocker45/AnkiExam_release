from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import *
from anki.notes import Note



#Main selection window to all for various AnkiExam tools
# ...existing imports...

DEBUG = False

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
    dlg = QDialog(mw)
    dlg.setWindowTitle("AnkiExam Tool Selection")
    dlg.setStyleSheet("background-color: #ff91da; color: white; font-weight: bold; font-size: 16px;")
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

    label = QLabel("Welcome to the AnkiExam Tool Selection!\n\n"
                   "Please select a tool from the menu bar.\n\n")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    # Button 1: Input Training Data
    def on_training():
        showInfo("To be implemented: Input Training Data")
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

#Here is eventually where i will feed through the question from the training data:
#DYNAMIC_STRING = "This is a dynamic string. Change me as needed!"
QuestionToAsk = "What is the capital of Canada?"
#DYNAMIC_STRING = "What is the capital of Canada?"

#a new custom gui funciton
def show_custom_gui():
    dlg = QDialog(mw)
    dlg.setWindowTitle("AnkiExam Tool")
    dlg.setMinimumWidth(800)
    dlg.setMinimumHeight(200)
    dlg.setStyleSheet("background-color: #ff91da; color: white; font-weight: bold; font-size: 16px;")
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)  # Align content to top

    label = QLabel("Please enter your answer to the question below.\n\n")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    # Dynamic string label
    dynamic_label = QLabel(QuestionToAsk)
    dynamic_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    dynamic_label.setStyleSheet("font-size: 13px; color: #222; background: transparent;")
    layout.addWidget(dynamic_label)

    input_field = QLineEdit()
    input_field.setPlaceholderText("Type your question here...")
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
            showInfo("Please enter a question.")
            return
        try:
            from .main import together_api_input
            output, total_tokens = together_api_input(user_answer_input_field, QuestionToAsk)
        except Exception as e:
            showInfo(f"API Error: {e}")
            return
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




