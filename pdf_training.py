from aqt import mw
from aqt.qt import *
from aqt.utils import showInfo
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QFileDialog, QTextEdit, QProgressBar, QHBoxLayout
from PyQt6.QtCore import QThread, pyqtSignal, QEventLoop
import time
import subprocess
import sys
from datetime import datetime

from .models import uploaded_txt_content, QuestionWorker
from .shared import require_access_key, questions_cycle
from .AnkiExamCard import add_questions_to_deck




def train_model_on_text(text_content):
    """
    Train the model on the provided text content.
    This function is called from both the GUI and programmatically.
    """
    # Store the text content in the global variable
    uploaded_txt_content["content"] = text_content
    
    # Create and run the worker
    worker = QuestionWorker()
    
    # Use an event loop to wait for the worker to finish
    loop = QEventLoop()
    
    def on_finished(questions_text, questions_list):
        # Store the questions in a dictionary for later use
        questions_cycle["index"] = 0
        questions_cycle["questions"] = questions_list
        
        # Create a new deck and add questions to it
        if mw.col is not None:
            # Create a new deck with default name in AnkiExamCard
            add_questions_to_deck()
        else:
            showInfo("Could not create deck: Anki collection not available")
        
        loop.quit()
    
    def on_error(error_msg):
        raise Exception(f"Error generating questions: {error_msg}")
    
    worker.finished.connect(on_finished)
    worker.error.connect(on_error)
    worker.start()
    
    # Wait for the worker to finish
    loop.exec()

def read_file_content(file_path: str) -> str:
    """Read content from either a TXT or PDF file."""
    if file_path.lower().endswith('.pdf'):
        try:
            # Try to import pypdf
            try:
                from pypdf import PdfReader
            except ImportError:
                raise ImportError("PDF support requires the pypdf package. Please install it using pip install pypdf")
                
            with open(file_path, "rb") as f:
                reader = PdfReader(f)
                text = "\n\n".join([page.extract_text() or '' for page in reader.pages])
            if len(text) > 400000:
                raise ValueError("PDF is too long")
            return text
        except Exception as e:
            raise Exception(f"Error reading PDF: {str(e)}")
    else:  # Assume TXT file
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

def show_txt_training_gui():
    dlg = QDialog(mw)
    dlg.setWindowTitle("Upload Training Content")
    dlg.setMinimumWidth(800)
    dlg.setMinimumHeight(600)
    layout = QVBoxLayout()
    layout.setAlignment(Qt.AlignmentFlag.AlignTop)

    label = QLabel(
        "\n\nInstructions: You can either:\n\n"
        "1. Upload a PDF file directly (we'll extract the text)\n"
        "2. Upload a TXT file\n"
        "3. Use ChatGPT/LLM to convert your content and paste it below\n\n"
        "When using ChatGPT/LLM, use this prompt:\n"
        "'Convert the attached data to text, extracting the important context from images\n"
        "and converting into plain text, so that no understanding is lost.\n"
        "Infer the essential story being presented within the slides from the images.'\n"
    )
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(label)

    file_label = QLabel("")
    file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(file_label)

    # Create a horizontal layout for upload buttons
    upload_layout = QHBoxLayout()
    
    upload_txt_btn = QPushButton("Upload TXT")
    upload_pdf_btn = QPushButton("Upload PDF")
    
    upload_layout.addWidget(upload_txt_btn)
    upload_layout.addWidget(upload_pdf_btn)
    
    # Add the upload buttons layout to the main layout
    btn_container = QWidget()
    btn_container.setLayout(upload_layout)
    layout.addWidget(btn_container)

    text_area = QTextEdit()
    text_area.setPlaceholderText("Paste your text content here or upload a file...")
    layout.addWidget(text_area)

    ok_btn = QPushButton("OK")
    ok_btn.setVisible(False)
    layout.addWidget(ok_btn)

    train_model_btn = QPushButton("Train Model on Content")
    train_model_btn.setVisible(False)
    layout.addWidget(train_model_btn)

    def handle_file_content(content):
        """Common handler for file content"""
        text_area.setPlainText(content)
        uploaded_txt_content["content"] = content
        showInfo("Content loaded successfully.")
        ok_btn.setVisible(True)
        train_model_btn.setVisible(True)

    def on_upload_txt():
        file_path, _ = QFileDialog.getOpenFileName(dlg, "Select TXT File", "", "Text Files (*.txt)")
        if file_path:
            file_label.setText(f"Selected: {file_path}")
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                handle_file_content(content)
            except Exception as e:
                text_area.setPlainText(f"Error reading file: {e}")
                uploaded_txt_content["content"] = ""
                ok_btn.setVisible(False)
                train_model_btn.setVisible(False)

    def on_upload_pdf():
        file_path, _ = QFileDialog.getOpenFileName(dlg, "Select PDF File", "", "PDF Files (*.pdf)")
        if file_path:
            file_label.setText(f"Selected: {file_path}")
            try:
                content = read_file_content(file_path)
                handle_file_content(content)
            except Exception as e:
                text_area.setPlainText(f"Error reading PDF: {e}")
                uploaded_txt_content["content"] = ""
                ok_btn.setVisible(False)
                train_model_btn.setVisible(False)

    def on_ok():
        dlg.accept()
        from .__init__ import selection_window_gui
        selection_window_gui()

    def on_train_model():
        # Make sure we have content
        content = text_area.toPlainText().strip()
        if not content:
            showInfo("Please enter or upload some content first.")
            return
            
        train_model_btn.setEnabled(False)

        # Show loading dialog
        loading_dialog = QDialog(dlg)
        loading_dialog.setWindowTitle("Loading...")
        loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)
        loading_layout = QVBoxLayout()
        loading_label = QLabel("Generating questions, please wait...")
        loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        loading_layout.addWidget(loading_label)
        progress = QProgressBar()
        progress.setRange(0, 0)
        loading_layout.addWidget(progress)
        loading_dialog.setLayout(loading_layout)
        loading_dialog.setMinimumWidth(400)
        loading_dialog.setMinimumHeight(120)
        loading_dialog.show()
        loading_dialog.raise_()
        loading_dialog.activateWindow()
        QApplication.processEvents()

        try:
            train_model_on_text(content)
            loading_dialog.close()
            showInfo(f"Generated {len(questions_cycle['questions'])} questions from the content.")
            
            # Show results in a modal dialog
            output_dialog = QDialog(dlg)
            output_dialog.setWindowTitle("Questions generated")
            output_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            output_dialog.setMinimumWidth(700)
            output_dialog.setMinimumHeight(500)
            output_layout = QVBoxLayout()
            output_text = QTextEdit()
            output_text.setReadOnly(True)
            output_text.setPlainText("\n".join(questions_cycle["questions"]))
            output_layout.addWidget(output_text)
            close_btn = QPushButton("Close")
            close_btn.clicked.connect(output_dialog.accept)
            output_layout.addWidget(close_btn)
            output_dialog.setLayout(output_layout)
            output_dialog.exec()
            
        except Exception as e:
            loading_dialog.close()
            showInfo(f"An error occurred:\n{str(e)}")
        finally:
            train_model_btn.setEnabled(True)

    upload_txt_btn.clicked.connect(on_upload_txt)
    upload_pdf_btn.clicked.connect(on_upload_pdf)
    ok_btn.clicked.connect(on_ok)
    train_model_btn.clicked.connect(on_train_model)

    dlg.setLayout(layout)
    dlg.exec()