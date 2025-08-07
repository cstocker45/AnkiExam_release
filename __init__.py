from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import *
from anki.notes import Note
from . import AnkiExamCard
from .pdf_training import read_file_content
from .shared import credential_manager, questions_cycle
from .ClientAuth import AuthClient
from PyQt6.QtCore import QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QEvent, QObject, QTimer
from PyQt6.QtGui import QIcon, QScreen, QColor, QPixmap, QMovie
from PyQt6.QtWidgets import QGraphicsDropShadowEffect, QDialog, QVBoxLayout, QLabel, QComboBox, QSizePolicy
from .settings_dialog import SettingsDialog
from PyQt6.QtCore import Qt, QSize
import os
import uuid
import re
from datetime import datetime
import time
from .models import uploaded_txt_content, QuestionWorker
from aqt import gui_hooks
from .shared import require_access_key, get_model_name

# Create a single AuthClient instance to be used throughout the addon
auth_client = AuthClient()
import platform



#initialize uploaded pdf content
uploaded_txt_content = {"content": ""}

# Import questions_cycle from shared instead of redefining it
from .shared import questions_cycle

# Initialize status bar with token display
from . import status_bar

DEBUG = False
#Integration of login box for authentication
auth_client = ClientAuth.AuthClient()

# Persistent device UUID logic (store in hidden OS-specific config dir)
def get_device_id_path():
    if platform.system() == "Windows":
        base = os.getenv("APPDATA") or os.getenv("LOCALAPPDATA")
        if not base:
            base = os.path.expanduser("~")
        dir_path = os.path.join(base, "AnkiExam")
    elif platform.system() == "Darwin":
        dir_path = os.path.expanduser("~/Library/Application Support/AnkiExam")
    else:
        dir_path = os.path.expanduser("~/.config/AnkiExam")
    os.makedirs(dir_path, exist_ok=True)
    return os.path.join(dir_path, ".device_id")

def get_or_create_device_id():
    path = get_device_id_path()
    if os.path.exists(path):
        with open(path, "r") as f:
            return f.read().strip()
    device_id = str(uuid.uuid4())
    with open(path, "w") as f:
        f.write(device_id)
    return device_id
DEVICE_ID = get_or_create_device_id()

# Automatically attempt login with saved credentials on startup
def auto_login_on_startup():
    saved_creds = credential_manager.load_credentials()
    if saved_creds:
        username = saved_creds.get('username')
        password = saved_creds.get('password')
        if auth_client.login(username, password):
            print("Auto-login successful")
        else:
            print("Auto-login failed")
    else:
        print("No saved credentials found")

auto_login_on_startup()



def show_verification_dialog(username):
    verify_dlg = QDialog(mw)
    verify_dlg.setWindowTitle("Verify Your Account")
    verify_layout = QVBoxLayout()
    
    # Instructions
    instructions = QLabel("Please check your email for the verification code\nand enter it below:")
    instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
    verify_layout.addWidget(instructions)
    
    # Code input
    code_input = QLineEdit()
    code_input.setPlaceholderText("Enter verification code")
    code_input.setFixedHeight(36)
    code_input.setStyleSheet("font-weight: bold; color: black; background-color: white; border-radius: 4px; font-size: 12px;")
    verify_layout.addWidget(code_input)
    
    # Status label
    status_label = QLabel("")
    status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    verify_layout.addWidget(status_label)
    
    # Verify button
    verify_btn = QPushButton("Verify")
    verify_btn.setStyleSheet("font-weight: bold; color: white; background-color: #4CAF50; border-radius: 4px; font-size: 14px;")
    verify_layout.addWidget(verify_btn)
    
    verify_dlg.setLayout(verify_layout)
    verify_dlg.setMinimumWidth(300)
    
    def do_verify():
        code = code_input.text().strip()
        if not code:
            status_label.setText("Please enter the verification code.")
            status_label.setStyleSheet("color: red;")
            return
            
        success, msg = auth_client.verify_code(username, code)
        status_label.setText(msg)
        if success:
            status_label.setStyleSheet("color: green;")
            verify_dlg.accept()
        else:
            status_label.setStyleSheet("color: red;")
    
    verify_btn.clicked.connect(do_verify)
    return verify_dlg.exec()

# Import token history manager
from .token_history import token_history

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
            # Call the API for answer checking
            from .main import together_api_input
            output, total_tokens = together_api_input(self.user_answer, self.question)
            print(f"API returned total_tokens: {total_tokens}")  # Debug logging

            # Track token usage
            if total_tokens > 0:
                # Use the auth_client from parent module
                if auth_client and auth_client.is_authenticated():
                    success = auth_client.add_tokens(total_tokens)
                    print(f"Token update success: {success}")  # Debug logging
                else:
                    print("Warning: auth_client not available or not authenticated")
                    
            # Emit the results
            self.finished.emit(output, total_tokens)
        except Exception as e:
            print(f"Error in AnswerWorker: {str(e)}")  # Debug logging
            self.error.emit(str(e))
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

def get_icon_path(icon_name):
    """Get the absolute path to an icon file"""
    return os.path.join(os.path.dirname(__file__), 'icons', icon_name)

#Main selection window to all for various AnkiExam tools
def selection_window_gui():
    # Login form fields (define once and use everywhere)
    user_input = QLineEdit()
    user_input.setPlaceholderText("Username")
    pass_input = QLineEdit()
    pass_input.setPlaceholderText("Password")
    pass_input.setEchoMode(QLineEdit.EchoMode.Password)
    email_input = QLineEdit()
    email_input.setPlaceholderText("Email (for registration)")
    remember_checkbox = QCheckBox("Remember me")

    def do_login():
        username = user_input.text().strip()
        password = pass_input.text().strip()
        #showInfo(password)
        if not username or not password:
            status_label.setText("Please enter both username and password.")
            return
        # Debug: print password length for troubleshooting
        print(f"Login attempt: username='{username}', password length={len(password)}")
        if auth_client.login(username, password):
            if remember_checkbox.isChecked():
                credential_manager.save_credentials(
                    username, 
                    password,
                    auth_client.get_access_key()
                )
            else:
                credential_manager.clear_credentials()
            login_form.hide()
            tools_section.show()
            # Shrink sidebar for tool icons
            sidebar.setFixedWidth(60)  # Smaller width for icons with padding
            sidebar_layout.setContentsMargins(1, 20, 1, 20)  # Adjust margins
        else:
            status_label.setText("Login failed. Try again.")

    # Support pressing Enter in password field to trigger login
    pass_input.returnPressed.connect(do_login)
    # Get the primary screen and set default dimensions
    window_width = 1024  # Default width
    window_height = 768  # Default height
    
    screen = QApplication.primaryScreen()
    if screen:
        screen_geometry = screen.geometry()
        # Calculate 70% of screen dimensions
        window_width = int(screen_geometry.width() * 0.7)
        window_height = int(screen_geometry.height() * 0.7)

    class PersistentDialog(QDialog):
        def closeEvent(self, event):
            # Only hide the dialog, don't destroy it
            event.ignore()
            self.hide()

    dlg = PersistentDialog(mw)
    dlg.setWindowTitle("AnkiExam Tool")
    dlg.setFixedSize(window_width, window_height)
    
    # Main layout is horizontal to accommodate sidebar and content
    main_layout = QHBoxLayout()
    dlg.setLayout(main_layout)

    # Create sidebar
    sidebar = QWidget()
    sidebar.setFixedWidth(200)  # Initial width for login form
    sidebar.setStyleSheet("""
        QWidget {
            background-color: #2c3e50;
            border: none;
        }
        QPushButton {
            border: none;
            padding: 15px;
            margin: 5px;
            border-radius: 10px;
            background-color: transparent;
            color: white;
        }
        QPushButton:hover {
            background-color: #34495e;
            border: 0px solid #FFFF00;  /* Yellow border */
        }
        QToolTip {
            background-color: #2c3e50;
            color: white;
            border: 0px solid #34495e;
            padding: 5px;
        }
        QLineEdit {
            padding: 8px;
            margin: 5px;
            border-radius: 4px;
            background-color: #34495e;
            color: white;
            border: 0px solid #455d7a;
            width: 180px;  /* Fixed width for input fields */
        }
        QLineEdit:focus {
            border: 0px solid #74b9ff;
        }
        QLabel {
            color: white;
            margin: 5px;
            border: none;
        }
        QCheckBox {
            color: white;
            margin: 5px;
            border: none;
        }
    """)
    
    sidebar_layout = QVBoxLayout()
    sidebar_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
    sidebar_layout.setSpacing(10)
    sidebar_layout.setContentsMargins(10, 20, 10, 20)

    # Create login form in sidebar
    login_form = QWidget()
    login_form_layout = QVBoxLayout()
    login_form.setLayout(login_form_layout)

    login_form_layout.addWidget(QLabel("Login"))
    login_form_layout.addWidget(user_input)
    login_form_layout.addWidget(pass_input)
    login_form_layout.addWidget(email_input)
    login_form_layout.addWidget(remember_checkbox)

    # Login buttons
    login_btn = QPushButton("Login")
    register_btn = QPushButton("Register")
    status_label = QLabel("")
    status_label.setWordWrap(True)
    status_label.setStyleSheet("color: #ff6b6b;")  # Red for errors

    login_form_layout.addWidget(login_btn)
    login_form_layout.addWidget(register_btn)
    login_form_layout.addWidget(status_label)

    # Add login form to sidebar
    sidebar_layout.addWidget(login_form)
    
    # Create tools section (initially hidden)
    tools_section = QWidget()
    tools_section.setStyleSheet("border: none;")
    tools_layout = QVBoxLayout()
    tools_layout.setContentsMargins(5, 0, 5, 0)
    tools_layout.setSpacing(5)
    tools_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)
    tools_section.setLayout(tools_layout)
    tools_section.hide()

    def open_settings(self):
        dialog = SettingsDialog(self)
        dialog.exec()

    # Create sidebar buttons with icons
    def create_sidebar_button(icon_name, tooltip, on_click):
        # Create a container for the button and tooltip
        container = QWidget()
        container_layout = QHBoxLayout()
        container_layout.setContentsMargins(0, 0, 0, 0)
        container_layout.setSpacing(0)
        container.setLayout(container_layout)
        
        # Create the button
        btn = QPushButton()
        btn.setFixedSize(50, 50)
        btn.setIcon(QIcon(get_icon_path(icon_name)))
        btn.setIconSize(QSize(30, 30))
        btn.clicked.connect(on_click)
        
        # Add widgets to container
        container_layout.addWidget(btn)
        container_layout.addStretch()
        
        # Create tooltip box at main window level
        tooltip_box = QWidget(mw)
        tooltip_box.setFixedHeight(50)
        tooltip_box.setStyleSheet("""
            QWidget {
                background-color: transparent;  /* Start transparent */
                border-radius: 0px;
                border: 0px solid #FFFF00;  /* Yellow border */
            }
        """)
        tooltip_box.hide()
        
        # Create inner box that will have the color and border
        inner_box = QWidget(tooltip_box)
        inner_box.setStyleSheet("""
            QWidget {
                background-color: #34495e;  
                border-radius: 4px;
                border: 0px solid #FFFF00;  /* Yellow border */
            }
        """)
        inner_box.setFixedHeight(50)
        
        # Create layout for inner box
        inner_layout = QHBoxLayout(inner_box)
        inner_layout.setContentsMargins(5, 0, 5, 0)
        inner_layout.setSpacing(0)
        
        # Create a background widget for the layout
        layout_bg = QWidget(inner_box)
        layout_bg.setStyleSheet("background-color: #34495e; border: none; border: 0px solid #FFFF00;")  # Bright green
        inner_layout.addWidget(layout_bg)
        
        # Create tooltip label inside the box
        tooltip_label = QLabel(tooltip)
        tooltip_label.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        tooltip_label.setStyleSheet("""
            QLabel {
                color: white;
                font-family: Helvetica, Arial, sans-serif;
                font-size: 15px;
                background-color: #34495e;  
                padding: 5px;
                border: 0px solid #00FFFF;  /* Cyan border */
            }
        """)
        
        # Add label to inner layout
        inner_layout.addWidget(tooltip_label)
        
        # Create layout for main tooltip box
        tooltip_layout = QHBoxLayout(tooltip_box)
        tooltip_layout.setContentsMargins(0, 0, 0, 0)
        tooltip_layout.setSpacing(0)
        tooltip_layout.addWidget(inner_box)
        
        # Calculate the width needed for the text
        tooltip_label.adjustSize()
        text_width = tooltip_label.sizeHint().width() + 50  # Add padding
        
        # Set window flags for tooltip box to stay on top
        tooltip_box.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.Tool |
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        # Create width animation for inner box
        anim = QPropertyAnimation(inner_box, b"geometry")
        anim.setDuration(300)  # 300ms animation
        
        def on_hover_enter():

            # Stop any running animations
            anim.stop()
            
            # Disconnect any existing finished signals
            try:
                anim.finished.disconnect()
            except:
                pass
                
            # Calculate position for tooltip box
            global_pos = container.mapToGlobal(container.rect().topRight())
            tooltip_box.setGeometry(QRect(global_pos.x(), global_pos.y(), text_width, 50))
            
            # Configure animation for expanding inner box
            start_rect = QRect(0, 0, 0, 50)
            end_rect = QRect(0, 0, text_width, 50)
            
            # Configure animation for expanding
            anim.setStartValue(start_rect)
            anim.setEndValue(end_rect)
            anim.setEasingCurve(QEasingCurve.Type.InExpo)  # Slow start, fast end
            
            # Set initial geometry and show
            inner_box.setGeometry(start_rect)
            tooltip_box.show()
            tooltip_box.raise_()
            anim.start()
        
        def on_hover_leave():
            # Stop any running animations
            anim.stop()
            
            # Disconnect any existing finished signals
            try:
                anim.finished.disconnect()
            except:
                pass
                
            # Configure animation for collapsing inner box
            start_rect = inner_box.geometry()
            end_rect = QRect(0, 0, 0, 50)
            
            # Configure animation for collapsing
            anim.setStartValue(start_rect)
            anim.setEndValue(end_rect)
            anim.setEasingCurve(QEasingCurve.Type.OutExpo)  # Fast start, slow end
            
            # Hide tooltip after animation finishes
            def on_anim_finished():
                tooltip_box.hide()
            anim.finished.connect(on_anim_finished)
            
            anim.start()
        
        # Install event filter for hover events
        class HoverFilter(QObject):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.hover_enter = on_hover_enter
                self.hover_leave = on_hover_leave
                
            def eventFilter(self, obj, event):
                if event.type() == QEvent.Type.Enter:
                    self.hover_enter()
                    return True
                elif event.type() == QEvent.Type.Leave:
                    self.hover_leave()
                    return True
                return False
        
        # Apply event filter to both container and button
        hover_filter = HoverFilter(container)
        container.installEventFilter(hover_filter)
        btn.installEventFilter(hover_filter)
        
        # Enable mouse tracking
        container.setMouseTracking(True)
        btn.setMouseTracking(True)
        
        # Set initial style
        container.setStyleSheet("""
            QWidget {
                background-color: transparent;
                border: none;
                border-radius: 0px;
            }
            QPushButton {
                border: none;
                border-radius: 0px;
                background-color: transparent;
                padding: 10px;
            }
        """)
        
        # Make sure the container accepts hover events
        container.setAttribute(Qt.WidgetAttribute.WA_Hover)
        btn.setAttribute(Qt.WidgetAttribute.WA_Hover)
        
        return container



    def do_register():
        username = user_input.text().strip()
        password = pass_input.text().strip()
        email = email_input.text().strip()
        if not username or not password or not email:
            status_label.setText("Please enter username, password, and email.")
            return
        device_id = DEVICE_ID
        success, msg = auth_client.register(username, password, email, device_id)
        status_label.setText(str(msg))
        if success:
            status_label.setStyleSheet("color: #51cf66;")  # Green for success
            verify_dlg = show_verification_dialog(username)
            if verify_dlg:  # If verification was successful
                do_login()  # Attempt to log in automatically
        else:
            status_label.setStyleSheet("color: #ff6b6b;")  # Red for errors

    def do_logout():
        auth_client.clear_auth()
        credential_manager.clear_credentials()
        user_input.clear()
        pass_input.clear()
        email_input.clear()
        remember_checkbox.setChecked(False)
        tools_section.hide()
        login_form.show()
        # Restore sidebar width for login form
        sidebar.setFixedWidth(200)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)
        # Close the dialog when explicitly logging out
        dlg.accept()

    def create_training_content(content_area):
        # Clear existing content
        for i in reversed(range(content_area.layout().count())): 
            content_area.layout().itemAt(i).widget().setVisible(False)
            content_area.layout().itemAt(i).widget().deleteLater()
            
        layout = content_area.layout()
        
        # Add title
        title = QLabel("Training Data Input")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            color: #2d3436;
            margin: 20px;
            font-weight: bold;
        """)
        layout.addWidget(title)

        # Add instructions
        instructions = QLabel(
            "\n\nInstructions: Use ChatGPT or another LLM to Input a PDF or other accepted format of your lecture notes or slides from your Professor."
            "\n\nWhile doing so provide the prompt: \n\n'Convert the attached data to a downloadable .txt file, extracting the important context from images and converting into plain text, so that no understanding is lost. \nInfer the essential story being presented within the slides from the images.'"
            "\n\nNext, upload your TXT file below, or paste your content directly in the text area."
        )
        instructions.setAlignment(Qt.AlignmentFlag.AlignCenter)
        instructions.setWordWrap(True)
        instructions.setStyleSheet("""
            font-size: 14px;
            color: #2d3436;
            margin: 20px;
        """)
        layout.addWidget(instructions)

        # Add file upload section
        file_label = QLabel("")
        file_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        file_label.setStyleSheet("color: #2d3436; margin: 10px;")
        layout.addWidget(file_label)

        # Create button container
        btn_container = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # Upload file button
        upload_btn = QPushButton("Upload .TXT")
        upload_btn.setFixedWidth(200)
        upload_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        
        # Use deck button
        use_deck_btn = QPushButton("Use Existing Deck")
        use_deck_btn.setFixedWidth(200)
        use_deck_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                padding: 10px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)

        #Create an input field for how many questions to generate
        num_questions_input = QLineEdit()
        num_questions_input.setPlaceholderText("How many questions to generate?")
        num_questions_input.setFixedWidth(200)
        num_questions_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
                background-color: white;
                margin: 10px;
                color: #2d3436;
            }
        """)
        btn_layout.addWidget(num_questions_input)
        num_questions_input.setValidator(QIntValidator())
        


        btn_layout.addWidget(upload_btn)
        btn_layout.addWidget(use_deck_btn)
        btn_container.setLayout(btn_layout)
        layout.addWidget(btn_container)
        
        # Add text input area
        text_input = QTextEdit()
        text_input.setPlaceholderText("Paste your training text here or upload a file...")
        text_input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                padding: 10px;
                font-size: 14px;
                background-color: white;
                margin: 10px;
                color: #2d3436;
            }
        """)
        layout.addWidget(text_input)
        
        # Add train button
        train_btn = QPushButton("Generate Questions")
        train_btn.setFixedWidth(200)
        train_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;  /* Match the AnkiExam blue theme */
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #2980b9;  /* Darker blue on hover */
            }
            QPushButton:disabled {
                background-color: #bdc3c7;  /* Gray when disabled */
            }
        """)
        btn_container = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(train_btn)
        btn_container.setLayout(btn_layout)
        layout.addWidget(btn_container)

        def on_upload():
            file_path, _ = QFileDialog.getOpenFileName(None, "Select File", "", "All Supported Files (*.txt);;Text Files (*.txt);;PDF Files (*.pdf)")
            if file_path:
                file_label.setText(f"Selected: {file_path}")
                try:
                    content = read_file_content(file_path)
                    text_input.setPlainText(content)
                    uploaded_txt_content["content"] = content  # Update the shared variable
                    showInfo("File content loaded successfully.")
                except Exception as e:
                    text_input.setPlainText(f"Error reading file: {e}")
                    uploaded_txt_content["content"] = ""
        
        def on_use_deck():
            content = extract_deck_content()
            if content:
                text_input.setPlainText(content)
                uploaded_txt_content["content"] = content
                showInfo("Deck content loaded successfully.")
        
        
        def on_train():
            from .pdf_training import train_model_on_text
            from .shared import questions_cycle  # Ensure shared is imported in this scope
            
            train_btn.setEnabled(False)
            train_btn.setText("Generating...")

            # Show loading indicator
            progress = QProgressBar()
            progress.setRange(0, 0)
            layout.addWidget(progress)

            try:
                # Update the questions_cycle before training
                questions_cycle["questions"] = []
                questions_cycle["index"] = 0
                
                train_model_on_text(text_input.toPlainText())
                progress.hide()
                train_btn.setEnabled(True)
                train_btn.setText("Generate Questions")
                #create_question_content(content_area)
            except Exception as e:
                progress.hide()
                train_btn.setEnabled(True)
                train_btn.setText("Generate Questions")
                showInfo(f"Error: {str(e)}")


        upload_btn.clicked.connect(on_upload)
        use_deck_btn.clicked.connect(on_use_deck)
        train_btn.clicked.connect(on_train)



    #Deprecated function which allows the user to review questions in the ankiexam app.
   #def create_question_content(content_area):
   #    # Clear existing content
   #    for i in reversed(range(content_area.layout().count())): 
   #        content_area.layout().itemAt(i).widget().setVisible(False)
   #        content_area.layout().itemAt(i).widget().deleteLater()
   #        
   #    layout = content_area.layout()
   #    
   #    from .pdf_training import questions_cycle
   #    questions = questions_cycle["questions"]
   #    idx = questions_cycle["index"]
   #    
   #    if not questions or idx >= len(questions):
   #        # Show no questions message
   #        msg = QLabel("No questions available.\nPlease input training data first.")
   #        msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
   #        msg.setStyleSheet("""
   #            font-size: 18px;
   #            color: #2d3436;
   #            margin: 20px;
   #        """)
   #        layout.addWidget(msg)
   #        return
   #        
   #    question = questions[idx]
   #    
   #    # Add question label
   #    question_label = QLabel("Please answer the following question:")
   #    question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
   #    question_label.setStyleSheet("""
   #        font-size: 18px;
   #        color: #2d3436;
   #        margin: 20px;
   #    """)
   #    layout.addWidget(question_label)
   #    
   #    # Add the actual question
   #    question_text = QLabel(question)
   #    question_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
   #    question_text.setWordWrap(True)
   #    question_text.setStyleSheet("""
   #        font-size: 24px;
   #        color: #2d3436;
   #        margin: 20px;
   #        font-weight: bold;
   #    """)
   #    layout.addWidget(question_text)
   #    
   #    # Add answer input
   #    answer_input = QLineEdit()
   #    answer_input.setPlaceholderText("Type your answer here...")
   #    answer_input.setFixedHeight(40)
   #    answer_input.setStyleSheet("""
   #        QLineEdit {
   #            border: 1px solid #dfe6e9;
   #            border-radius: 4px;
   #            padding: 10px;
   #            font-size: 16px;
   #            background-color: white;
   #            margin: 20px;
   #        }
   #    """)
   #    layout.addWidget(answer_input)
   #    
   #    # Add submit button
   #    submit_btn = QPushButton("Submit Answer")
   #    submit_btn.setFixedWidth(200)
   #    submit_btn.setStyleSheet("""
   #        QPushButton {
   #            background-color: #4CAF50;
   #            color: white;
   #            border: none;
   #            padding: 10px;
   #            border-radius: 4px;
   #            font-weight: bold;
   #        }
   #        QPushButton:hover {
   #            background-color: #45a049;
   #        }
   #    """)
   #    btn_container = QWidget()
   #    btn_layout = QHBoxLayout()
   #    btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
   #    btn_layout.addWidget(submit_btn)
   #    btn_container.setLayout(btn_layout)
   #    layout.addWidget(btn_container)
   #    
   #    def on_submit():
   #        if not answer_input.text().strip():
   #            showInfo("Please enter an answer.")
   #            return
   #            
   #        submit_btn.setEnabled(False)
   #        submit_btn.setText("Checking...")
   #        
   #        # Show loading indicator
   #        progress = QProgressBar()
   #        progress.setRange(0, 0)
   #        layout.addWidget(progress)
   #        
   #        # Create worker to handle answer checking
   #        worker = AnswerWorker(answer_input.text(), question)
   #        
   #        def on_finished(output, total_tokens):
   #            progress.hide()
   #            
   #            # Show result
   #            result_label = QLabel(f"Feedback:\n{output}\n\nTokens used: {total_tokens}")
   #            result_label.setWordWrap(True)
   #            result_label.setStyleSheet("""
   #                font-size: 16px;
   #                color: #2d3436;
   #                margin: 20px;
   #                padding: 20px;
   #                background-color: #f8f9fa;
   #                border-radius: 4px;
   #            """)
   #            layout.addWidget(result_label)
   #            
   #            # Add next question button if available
   #            questions_cycle["index"] += 1
   #            if questions_cycle["index"] < len(questions_cycle["questions"]):
   #                next_btn = QPushButton("Next Question")
   #                next_btn.setFixedWidth(200)
   #                next_btn.setStyleSheet("""
   #                    QPushButton {
   #                        background-color: #4CAF50;
   #                        color: white;
   #                        border: none;
   #                        padding: 10px;
   #                        border-radius: 4px;
   #                        font-weight: bold;
   #                    }
   #                    QPushButton:hover {
   #                        background-color: #45a049;
   #                    }
   #                """)
   #                next_btn.clicked.connect(lambda: create_question_content(content_area))
   #                
   #                btn_container = QWidget()
   #                btn_layout = QHBoxLayout()
   #                btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
   #                btn_layout.addWidget(next_btn)
   #                btn_container.setLayout(btn_layout)
   #                layout.addWidget(btn_container)
   #            else:
   #                done_label = QLabel("You have completed all questions!")
   #                done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
   #                done_label.setStyleSheet("""
   #                    font-size: 18px;
   #                    color: #2d3436;
   #                    
   #                    margin: 20px;
   #                """)
   #                layout.addWidget(done_label)
   #        
   #        def on_error(error_msg):
   #            progress.hide()
   #            submit_btn.setEnabled(True)
   #            submit_btn.setText("Submit Answer")
   #            showInfo(f"Error: {error_msg}")
   #        
   #        worker.finished.connect(on_finished)
   #        worker.error.connect(on_error)
   #        worker.start()
   #    
   #    submit_btn.clicked.connect(on_submit)

    def on_training():
        create_training_content(content_area)

   # def on_question():
   #     create_question_content(content_area)

    def open_settings():
        showInfo("Settings are not implemented yet. This is a placeholder function.")

    # Connect buttons to their functions
    login_btn.clicked.connect(do_login)
    register_btn.clicked.connect(do_register)

    # Create tool buttons
    def show_welcome():
        # Remove all widgets from content_layout
        for i in reversed(range(content_layout.count())):
            widget = content_layout.itemAt(i).widget()
            if widget is not None:
                widget.setParent(None)
        # Add welcome label
        welcome_label = QLabel("Welcome to AnkiExam Tool!")
        welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        welcome_label.setStyleSheet("font-size: 24px; color: #2d3436; margin: 20px; font-weight: bold;")
        content_layout.addWidget(welcome_label)

        #create tutorial
        tutorial_label = QLabel(
            "To get started, click on the Settings button in the sidebar to configure your AI model settings. "
            "<br><br>"
            "After selecting your personalized AI model, enhance your current decks by clicking the adjacent AnkiExam logo. "
            "Or, you may generate new decks by imputing your professors lecture notes or slides under the book icon."
        
        )
        tutorial_label.setWordWrap(True)
        tutorial_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tutorial_label.setStyleSheet("""
            font-size: 15px;
            color: #2d3436;
            margin: 30px;
        """)
        content_layout.addWidget(tutorial_label
        )


        # Add PayPal donation hyperlink
        paypal_label = QLabel(
            'AnkiExam cannot maintain its servers without your support. '
            'Please help the independent development of AnkiExam, and keep the addon free: '
            '<a href="https://www.paypal.com/donate/?hosted_button_id=DVZWGMNHTHN4Q" '
            'style="color:#2235e0;">Donate via PayPal</a>'
        )
        paypal_label.setStyleSheet("""
            font-size: 14px;
            color: #2d3436;
            margin: 10px;
        """)

        paypal_label.setOpenExternalLinks(True)
        paypal_label.setWordWrap(True)
        paypal_label.setFixedWidth(600)
        paypal_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        # Optional: adjust size policy for better layout behavior
        #paypal_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Maximum)
        content_layout.addWidget(paypal_label, alignment=Qt.AlignmentFlag.AlignCenter)

    home_btn = create_sidebar_button(
        "AnkiExam_Home.png",
        "Home",
        show_welcome
    )

    training_btn = create_sidebar_button(
        "book.svg",
        "Input Training Data",
        on_training
    )

    question_btn = create_sidebar_button(
        "question.png",
        "Input Question",
        open_settings
    )

    def on_stats():
        # Clear existing content
        for i in reversed(range(content_area.layout().count())): 
            content_area.layout().itemAt(i).widget().setVisible(False)
            content_area.layout().itemAt(i).widget().deleteLater()
            
        layout = content_area.layout()
        
        # Add title
        title = QLabel("Token Usage Statistics")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            color: #2d3436;
            margin: 20px;
            font-weight: bold;
        """)
        layout.addWidget(title)
        
        # Function to update the display with token usage
        def update_display(token_usage):
            # Add token usage display
            token_label = QLabel(f"Total Tokens Used: {token_usage:,}")
            token_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            token_label.setStyleSheet("""
                font-size: 36px;
                color: #2d3436;
                margin: 40px;
                padding: 20px;
                background-color: #f1f2f6;
                border-radius: 10px;
            """)
            layout.addWidget(token_label)

            # Add explanation
            explanation = QLabel(
                "Token usage is tracked for all your interactions with the AI model, including:\n"
                "• Question generation from training data\n"
                "• Answer evaluation and feedback\n\n"
                "Each token represents a piece of text processed by the AI model."
            )
            explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
            explanation.setWordWrap(True)
            explanation.setStyleSheet("""
                font-size: 16px;
                color: #2d3436;
                margin: 20px;
            """)
            layout.addWidget(explanation)

            # Add refresh button
            refresh_btn = QPushButton("Refresh Token Count")
            refresh_btn.setFixedWidth(200)
            refresh_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            btn_container = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(refresh_btn)
            btn_container.setLayout(btn_layout)
            layout.addWidget(btn_container)

            refresh_btn.clicked.connect(on_stats)  # Clicking refresh will reload the stats

        # Create token label first
        token_label = QLabel()
        token_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        token_label.setStyleSheet("""
            font-size: 24px;
            margin: 40px;
            padding: 20px;
            background-color: #f1f2f6;
            border-radius: 10px;
        """)
        
        # Get initial token usage
        try:
            token_usage = auth_client.get_token_usage()
            update_display(token_usage)
        except Exception as e:
            token_label.setText("Could not retrieve token usage. Please try again later.")
            token_label.setStyleSheet(token_label.styleSheet() + "\ncolor: #e74c3c;")
            layout.addWidget(token_label)

            # Add retry button
            retry_btn = QPushButton("Retry")
            retry_btn.setFixedWidth(200)
            retry_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    border: none;
                    padding: 10px;
                    border-radius: 4px;
                    font-weight: bold;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """)
            btn_container = QWidget()
            btn_layout = QHBoxLayout()
            btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            btn_layout.addWidget(retry_btn)
            btn_container.setLayout(btn_layout)
            layout.addWidget(btn_container)

            retry_btn.clicked.connect(on_stats)  # Clicking retry will reload the stats


    stats_btn = create_sidebar_button(
        "Stat_image.png",
        "Show Usage",
        on_stats
    )

    logout_btn = create_sidebar_button(
        "logout.png",
        "Logout",
        do_logout
    )

    # Create settings button
    def reset_main_window():
        # Clear existing content
        for i in reversed(range(content_area.layout().count())): 
            content_area.layout().itemAt(i).widget().setVisible(False)
            content_area.layout().itemAt(i).widget().deleteLater()

        layout = content_area.layout()
        
        # Add title
        title = QLabel("Model Settings")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("""
            font-size: 24px;
            color: #2d3436;
            margin: 20px;
            font-weight: bold;
        """)
        layout.addWidget(title)

        # Create model selection container
        model_container = QWidget()
        model_layout = QVBoxLayout()
        model_container.setLayout(model_layout)
        
        # Add model selection label
        model_label = QLabel("Select AI Model:")
        model_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        model_label.setStyleSheet("""
            font-size: 16px;
            color: #2d3436;
            margin: 20px;
        """)
        model_layout.addWidget(model_label)

        # Add model dropdown
        model_combo = QComboBox()
        model_combo.addItems([
            "DeepSeek R1 Distill Llama 70B Free",
            "DeepSeek V3-0324",
            "Llama 3.3 70B Instruct Turbo Free",
            "Llama 3.1 405B Instruct Turbo"
        ])
        # Disable non-free models
        non_free_labels = {"DeepSeek V3-0324", "Llama 3.1 405B Instruct Turbo"}
        from PyQt6.QtGui import QStandardItemModel
        model_obj = model_combo.model()
        if isinstance(model_obj, QStandardItemModel):
            for i in range(model_combo.count()):
                text = model_combo.itemText(i)
                if text in non_free_labels:
                    item = model_obj.item(i)
                    if item:
                        item.setEnabled(False)
        # Reflect current saved selection
        try:
            from .shared import get_model_name
            current_api_model = get_model_name()
            api_to_label = {
                "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free": "DeepSeek R1 Distill Llama 70B Free",
                "deepseek-ai/DeepSeek-V3": "DeepSeek V3-0324",
                "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free": "Llama 3.3 70B Instruct Turbo Free",
                "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo": "Llama 3.1 405B Instruct Turbo",
            }
            current_label = api_to_label.get(current_api_model, "DeepSeek R1 Distill Llama 70B Free")
            # If saved model is non-free, fall back to a free default
            if current_label in non_free_labels:
                current_label = "DeepSeek R1 Distill Llama 70B Free"
            model_combo.setCurrentText(current_label)
        except Exception:
            pass

        model_combo.setFixedWidth(300)
        model_combo.setStyleSheet("""
            QComboBox {
                padding: 8px;
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                background-color: white;
                color: #2d3436;
                font-size: 14px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(down_arrow.png);
                width: 12px;
                height: 12px;
            }
        """)
        
        # Center the combo box
        combo_container = QWidget()
        combo_layout = QHBoxLayout()
        combo_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        combo_layout.addWidget(model_combo)
        combo_container.setLayout(combo_layout)
        model_layout.addWidget(combo_container)

        # Add explanation text
        explanation = QLabel(
            "Select the AI model to use for question generation and answer evaluation.\n\n"
            "• DeepSeek R1 Distill Llama 70B Free: Optimized for efficiency\n"
            "• DeepSeek V3-0324: Latest model with enhanced capabilities"
        )
        explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        explanation.setWordWrap(True)
        explanation.setStyleSheet("""
            font-size: 16px;
            color: #2d3436;
            margin: 20px;
            padding: 20px;
            background-color: #f1f2f6;
            border-radius: 10px;
        """)
        model_layout.addWidget(explanation)

        # Add separator
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet("background-color: #dfe6e9; margin: 20px;")
        model_layout.addWidget(separator)

        # Add train button injection toggle
        toggle_container = QWidget()
        toggle_layout = QVBoxLayout()
        toggle_container.setLayout(toggle_layout)

        toggle_label = QLabel("Train Button Integration:")
        toggle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toggle_label.setStyleSheet("""
            font-size: 16px;
            color: #2d3436;
            margin: 20px;
        """)
        toggle_layout.addWidget(toggle_label)

        toggle_btn = QPushButton()
        from .shared import get_train_button_enabled, set_train_button_enabled
        is_enabled = get_train_button_enabled()
        
        def update_toggle_state():
            if get_train_button_enabled():
                toggle_btn.setText("Enabled")
                toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #4CAF50;
                        color: white;
                        border: none;
                        padding: 10px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 200px;
                    }
                    QPushButton:hover {
                        background-color: #45a049;
                    }
                """)
            else:
                toggle_btn.setText("Disabled")
                toggle_btn.setStyleSheet("""
                    QPushButton {
                        background-color: #e74c3c;
                        color: white;
                        border: none;
                        padding: 10px;
                        border-radius: 4px;
                        font-weight: bold;
                        min-width: 200px;
                    }
                    QPushButton:hover {
                        background-color: #c0392b;
                    }
                """)

        def toggle_train_button():
            current_state = get_train_button_enabled()
            set_train_button_enabled(not current_state)
            update_toggle_state()
            # Refresh the deck browser to show/hide train buttons
            mw.deckBrowser.refresh()

        toggle_btn.clicked.connect(toggle_train_button)
        update_toggle_state()  # Set initial state

        # Center the toggle button
        btn_container = QWidget()
        btn_layout = QHBoxLayout()
        btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_layout.addWidget(toggle_btn)
        btn_container.setLayout(btn_layout)
        toggle_layout.addWidget(btn_container)

        # Add toggle explanation
        toggle_explanation = QLabel(
            "Enable or disable the Train button integration.\n"
            "When enabled, Train buttons will be injected into Anki card editors.\n"
            "Changes will take effect after restarting Anki."
        )
        toggle_explanation.setAlignment(Qt.AlignmentFlag.AlignCenter)
        toggle_explanation.setWordWrap(True)
        toggle_explanation.setStyleSheet("""
            font-size: 14px;
            color: #2d3436;
            margin: 20px;
            padding: 20px;
            background-color: #f1f2f6;
            border-radius: 10px;
        """)
        toggle_layout.addWidget(toggle_explanation)
        
        model_layout.addWidget(toggle_container)

        def on_model_changed(index):
            model_name = model_combo.currentText()
            label_to_api = {
                "DeepSeek R1 Distill Llama 70B Free": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free",
                "DeepSeek V3-0324": "deepseek-ai/DeepSeek-V3",
                "Llama 3.3 70B Instruct Turbo Free": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
                "Llama 3.1 405B Instruct Turbo": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
            }
            # Guard against non-free selection
            if model_name in non_free_labels:
                model_name = "DeepSeek R1 Distill Llama 70B Free"
            api_model = label_to_api.get(model_name, "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free")
            # Update the model in shared configuration
            from .shared import update_model
            update_model(api_model)

        model_combo.currentIndexChanged.connect(on_model_changed)
        layout.addWidget(model_container)

    settings_btn = create_sidebar_button(
        "settings_icon.png",
        "Settings",
        reset_main_window
    )

    # Add buttons to tools section (home first)
    tools_layout.addWidget(home_btn)
    tools_layout.addWidget(training_btn)
    tools_layout.addWidget(question_btn)
    tools_layout.addWidget(stats_btn)
    tools_layout.addStretch()  # Push settings and logout to bottom
    tools_layout.addWidget(settings_btn)  # Settings just above logout
    tools_layout.addWidget(logout_btn)

    # Add tools section to sidebar
    sidebar_layout.addWidget(tools_section)
    sidebar.setLayout(sidebar_layout)

    # Create main content area
    content_area = QWidget()
    content_layout = QVBoxLayout()
    content_area.setLayout(content_layout)
    content_area.setStyleSheet("""
        QWidget {
            background-color: #f5f6fa;
        }
    """)

    # Add sidebar and content area to main layout
    main_layout.addWidget(sidebar)

    # Create scroll area
    scroll = QScrollArea()
    scroll.setWidget(content_area)
    scroll.setWidgetResizable(True)
    scroll.setStyleSheet("""
        QScrollArea {
            border: none;
            background-color: #f5f6fa;
        }
        QScrollBar:vertical {
            border: none;
            background: #f5f6fa;
            width: 10px;
            margin: 0px;
        }
        QScrollBar::handle:vertical {
            background: #cbd5e0;
            min-height: 20px;
            border-radius: 5px;
        }
        QScrollBar::add-line:vertical {
            height: 0px;
        }
        QScrollBar::sub-line:vertical {
            height: 0px;
        }
        QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
            background: none;
        }
    """)

    # Add scroll area to main layout instead of content area directly
    main_layout.addWidget(scroll)

    # Welcome message in content area (initial)
    show_welcome()


    # Set login form state based on credentials already loaded at startup
    saved_creds = credential_manager.load_credentials()
    if saved_creds:
        user_input.setText(saved_creds['username'])
        pass_input.setText(saved_creds['password'])
        remember_checkbox.setChecked(True)
        login_form.hide()
        tools_section.show()
        sidebar.setFixedWidth(60)
        sidebar_layout.setContentsMargins(1, 20, 1, 20)
    else:
        tools_section.hide()
        login_form.show()
        sidebar.setFixedWidth(200)
        sidebar_layout.setContentsMargins(10, 20, 10, 20)

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

def extract_deck_content(deck_name=None):
    """
    Extract text content from both front and back of cards in a specified deck.
    If no deck name is provided, shows a deck selection dialog.
    Returns the compiled text content.
    """
    if not mw.col:
        showInfo("Anki collection not available.")
        return None
        
    col = mw.col
    
    # If no deck specified, show deck selection dialog
    if deck_name is None:
        # Get list of deck names
        deck_names = [str(d['name']) for d in col.decks.all() if 'name' in d]
        if not deck_names:
            showInfo("No decks found.")
            return None
            
        # Create dialog for deck selection
        dlg = QDialog(mw)
        dlg.setWindowTitle("Select Deck")
        layout = QVBoxLayout()
        
        # Add deck selection combo box
        combo = QComboBox()
        combo.addItems(deck_names)
        layout.addWidget(combo)
        
        # Add OK button
        btn = QPushButton("OK")
        layout.addWidget(btn)
        
        dlg.setLayout(layout)
        
        # Store selected deck name
        selected_deck = [None]
        
        def on_accept():
            selected_deck[0] = combo.currentText()
            dlg.accept()
            
        btn.clicked.connect(on_accept)
        
        if not dlg.exec():
            return None
            
        deck_name = selected_deck[0]
        
        if not deck_name:
            return None
    
    # Get deck ID
    deck_id = col.decks.id(str(deck_name))
    if not deck_id:
        showInfo(f"Deck '{deck_name}' not found.")
        return None
    
    # Get all cards from the deck
    card_ids = col.find_cards(f"did:{deck_id}")
    if not card_ids:
        showInfo(f"No cards found in deck '{deck_name}'.")
        return None
    
    # Extract content from cards
    content = []
    for card_id in card_ids:
        card = col.get_card(card_id)
        note = card.note()
        
        # Get field names
        field_names = note.keys()
        
        # Extract text from each field
        for field in field_names:
            field_content = note[field]
            if field_content:
                # Remove HTML tags
                field_content = re.sub(r'<[^>]+>', '', field_content)
                if field_content.strip():
                    content.append(field_content.strip())
    
    # Join all content with double newlines
    return "\n\n".join(content)

#02.07.2025 for some reason decks with spaces are not being detected but those with no spaces are okay...
#this is an issue with the way these spaceare being stored in anki's backend.

@require_access_key
def train_from_deck(deck_id):
    """Train on cards from a specific deck by ID."""
    if not mw.col:
        showInfo("Anki collection not available.")
        return
        
    try:
        # Convert to integer in case it's a string
        deck_id = str(deck_id)
    except ValueError:
        showInfo(f"Invalid deck ID: {deck_id}")
        return
        
    # Get deck by ID
    deck = mw.col.decks.get(deck_id)
    if not deck:
        showInfo(f"Deck with ID {deck_id} not found")
        return
        
    deck_name = deck['name']
    #showInfo(f"Training from deck: {deck_name} (ID: {deck_id})")
    
    # Get all cards from the deck using ID
    card_ids = mw.col.find_cards(f"did:{deck_id}")
    #showInfo(f"Found {len(card_ids)} cards in deck")
    
    if not card_ids:
        showInfo(f"No cards found in deck '{deck_name}'")
        return
    
    # Get card contents
    cards_content = []
    for card_id in card_ids:
        card = mw.col.get_card(card_id)
        note = card.note()
        # Get the first field as content
        if note.fields:
            cards_content.append(note.fields[0])
    
    # Join all content with newlines
    combined_content = "\n\n".join(cards_content)
    
    # Store in uploaded_txt_content
    uploaded_txt_content["content"] = combined_content
    uploaded_txt_content["file_name"] = f"deck_{deck_name}.txt"
    
    # Debug: Check content before passing
    content_length = len(combined_content) if combined_content else 0
    #showInfo(f"Content length before training: {content_length} characters")
    
  
    try:
        # Save content to file
        addon_dir = os.path.dirname(__file__)
        content_file = os.path.join(addon_dir, "uploaded_txt_content.txt")
        
        #showInfo("Saving content to file...")
        with open(content_file, "w", encoding="utf-8") as f:
            f.write(combined_content)
        #showInfo(f"Saved deck content to {content_file}")
        
        # Start training on this content
        # Debug authentication state
        if not auth_client.is_authenticated():
            showInfo("Error: Not authenticated. Please log in again.")
            return

        try:
            # Get token usage before training
            usage_before = auth_client.get_token_usage()
            print(f"Token usage before training: {usage_before}")  # Debug logging
            
            #showInfo("Starting training process...")
            from .pdf_training import train_model_on_text
            train_model_on_text(combined_content)
            
            # Wait a moment for token usage to update on server
            time.sleep(3)  # Increased wait time to ensure server update
            
            # Get updated token usage
            current_usage = auth_client.get_token_usage()
            print(f"Token usage after training: {current_usage}")  # Debug logging
            
            # Calculate tokens used
            tokens_used = current_usage - usage_before
            print(f"Calculated tokens used: {tokens_used}")  # Debug logging
            
            if tokens_used <= 0:
                # If no tokens were counted, try getting the usage again
                time.sleep(2)
                current_usage = auth_client.get_token_usage()
                tokens_used = current_usage - usage_before
                
            model = get_model_name()
            if not model:
                showInfo("Error: No model selected. Please select a model in settings.")
                return
            
            # Log the training completion
            showInfo(f"Model  Used: {model}")
            
            # Show token usage information
            showInfo(f"Training completed!\n\nTokens used in this session: {tokens_used:,}\nTotal token usage: {current_usage:,}")
            
            
        except Exception as token_error:
            showInfo(f"Error getting token usage: {str(token_error)}")
        
    except Exception as e:
        showInfo(f"Error in train_from_deck: {str(e)}")
        import traceback
        showInfo(f"Traceback: {traceback.format_exc()}")
        # Try to log the error to a file as well
        try:
            error_log = os.path.join(addon_dir, "error_log.txt")
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} - Error in train_from_deck:\n")
                f.write(f"{str(e)}\n")
                f.write(f"{traceback.format_exc()}\n\n")
        except:
            pass  # If we can't log the error, at least we tried
    
def inject_train_buttons(*args):
    """Inject a train button next to each deck name in the deck browser."""
    # Only run if we're actually in the deck browser view
    if not mw.state == 'deckBrowser':
        return

    # Only inject if the webview exists and the feature is enabled
    if not hasattr(mw, 'deckBrowser') or not mw.deckBrowser or not mw.deckBrowser.web:
        return
        
    # Import the setting check
    from .shared import get_train_button_enabled
    if not get_train_button_enabled():
        # If disabled, remove any existing train buttons
        js = """
        // Remove existing train buttons
        $('.train-btn').remove();
        """
        mw.deckBrowser.web.eval(js)
        return

    #Here we also use base64 to directly embed the SVG icon in the button
    #This avoids needing to load an external image file, making it more portable.
    #the SVG is a simple train icon that will be displayed in the button
    js = """
    // Wait for the page to load
    setTimeout(function() {
        // For each deck row
        $('tr.deck').each(function() {
            var $row = $(this);
            var deckId = $row.attr('id');  // Get the deck ID from the row's id attribute
            var $deckLink = $row.find('a.deck');
            var deckName = $deckLink.text().trim();
        
            // Check if button already exists
            if ($row.find('.train-btn').length === 0) {
                    // Create and append the train button
                var $button = $('<button>')
                    .addClass('train-btn')
                    .append($('<img>')
                        .attr('src', 'data:image/png+xml;base64,iVBORw0KGgoAAAANSUhEUgAABGIAAATQCAYAAAC4MePhAAAAAXNSR0IArs4c6QAAAIRlWElmTU0AKgAAAAgABQESAAMAAAABAAEAAAEaAAUAAAABAAAASgEbAAUAAAABAAAAUgEoAAMAAAABAAIAAIdpAAQAAAABAAAAWgAAAAAAAAFKAAAAAQAAAUoAAAABAAOgAQADAAAAAQABAACgAgAEAAAAAQAABGKgAwAEAAAAAQAABNAAAAAAuBqwbwAAAAlwSFlzAAAywAAAMsABKGRa2wAAQABJREFUeAHs3QmUZcd5GOYazL5hNgxm5wKAILEQOzDAYDADm1S0hLYWarHkhI4YSbScyNbmKNRJItlOJNsSIx/H0WbFkRjrSHYsH8eWLDumpEiisHIHd1CQKJLYQewY7JP/itPATE9P93uv71JV97vn1Ol+y6366/sf0N3/3KqbkoMAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAgQIAAAQIECBAg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QIAAAQIECBAgUJ2AQkx1KTUhAgQIECBAgAABAgQIECBAIFcBhZhcMyMuAgQIECBAgAABAgQIECBAoDoBhZjqUmpCBAgQIECAAAECBAgQIECAQK4CCjG5ZkZcBAgQIECAAAECBAgQIECAQHUCCjHVpdSECBAgQIAAAQIECBAgQIAAgVwFFGJyzYy4CBAgQIAAAQIECBAgQIAAgeoEFGKqS6kJESBAgAABAgQIECBAgAABArkKKMTkmhlxESBAgAABAgQIECBAgAABAtUJKMRUl1ITIkCAAAECBAgQIECAAAECBHIVUIjJNTPiIkCAAAECBAgQIECAAAECBKoTUIipLqUmRIAAAQIECBAgQIAAAQIECOQqoBCTa2bERYAAAQIECBAgQIAAAQIECFQnoBBTXUpNiAABAgQIECBAgAABAgQIEMhVQCEm18yIiwABAgQIECBAgAABAgQIEKhOQCGmupSaEAECBAgQIECAAAECBAgQIJCrgEJMrpkRFwECBAgQIECAAAECBAgQIFCdgEJMdSk1IcFwuTAAAEAASURBVAIECBAgQIAAAQIECBAgQCBXAYWYXDMjLgIECBAgQIAAAQIECBAgQKA6AYWY6lJqQgQIECBAgAABAgQIECBAgECuAgoxuWZGXAQIECBAgAABAgQIECBAgEB1Agox1aXUhAgQIECAAAECBAgQIECAAIFcBRRics2MuAgQIECAAAECBAgQIECAAIHqBBRiqkupCREgQIAAAQIECBAgQIAAAQK5CijE5JoZcREgQIAAAQIECBAgQIAAAQLVCayqbkYmRIBAaQLHIuAHoj1TWuDiJUCAAAECHQusif53RNvW8Ti6J0CAAIEeBRRiesQ2FAECrwjcEt/9arT3Rbs72vFoDgIECBAgQGBhgZ3x9JFo3xztG6OtjeYgQIAAgUIFLE0qNHHCJlCowO0R940n2s/G189GU4QJBAcBAgQIEFhE4KF47TeifXu086L902h+fgaCgwABAiUKKMSUmDUxEyhT4O9H2IeiNVfDOAgQIECAAIHZBO6N074n2n8e7fHZunAWAQIECAwpoBAzpL6xCYxD4OWY5juivTta872DAAECBAgQWL7Ab0cX10f7wvK70gMBAgQI9CmgENOntrEIjFPgR2La/9c4p27WBAgQIECgU4FPR+9/OZoN7ztl1jkBAgTaFVCIaddTbwQInCrw6/Hwp099yiMCBAgQIECgRYGPRF//dYv96YoAAQIEOhZQiOkYWPcERizwRMz9b454/qZOgAABAgT6Emj+4eM/9DWYcQgQIEBgeQIKMcvzczYBAmcW+N/jpeYuDw4CBAgQIECge4Ef734IIxAgQIBAGwIKMW0o6oMAgYUEfmmhJz1HgAABAgQIdCJwe/R6Vyc965QAAQIEWhVQiGmVU2cECJwQ+ER8vYcGAQIECBAg0KvAv+t1NIMRIECAwEwCCjEzsTmJAIElBG5b4nUvEyBAgAABAu0L+PnbvqkeCRAg0LqAQkzrpDokQCAE/pgCAQIECBAg0LuAn7+9kxuQAAEC0wsoxExv5gwCBJYWeHzpt3gHAQIECBAg0LKAn78tg+qOAAECXQgoxHShqk8CBF5CQIAAAQIECPQu4Odv7+QGJECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkCAAAECBAgQIECAAAECBAhML6AQM72ZMwgQIECAAAECBAgQIECAAAECMwkoxMzE5iQCBAgQIECAAAECBAgQIECAwPQCCjHTmzmDAAECBAgQIECAAAECBAgQIDCTgELMTGxOIkBgCYEVS7zuZQIECBAgQKB9AT9/2zfVIwECBFoXUIhpnVSHBAiEwAYKBAgQIECAQO8Cfv72Tm5AAgQITC+gEDO9mTMIEFhaYP/Sb/EOAgQIECBAoGUBP39bBtUdAQIEuhBQiOlCVZ8ECFyOgAABAgQIEOhdwM/f3skNSIAAgekFFGKmN3MGAQJLCxyKt2xc+m3eQYAAAQIECLQo8FUt9qUrAgQIEOhIQCGmI1jdEhi5wLqY/7eM3MD0CRAgQIBAnwLnxmBf3eeAxiJAgACB2QQUYmZzcxYBAksL/HC8xf9jlnbyDgIECBAg0IbAD0Qnq9voSB8ECBAg0K2AP5K69dU7gTELXBKTf9eYAcydAAECBAj0JHB+jPP9PY1lGAIECBBYpoBCzDIBnU6AwKIC74lXr170HV4kQIAAAQIEliPQ7Mn2r6I1y4IdBAgQIFCAgEJMAUkSIoGCBdZH7P9PNLfTLDiJQidAgACBbAVWRmTvjXZFthEKjAABAgROE1CIOY3EEwQItCywL/q7Pdq1LferOwIECBAgMGaBbTH5/xDtm8aMYO4ECBAoUUAhpsSsiZlAeQJ7I+Q/iNasX2/+9c5BgAABAgQIzC5wc5x6R7S3zt6FMwkQIEBgKAGFmKHkjUtgfALN2vWfifbpaH8j2vZoDgIECBAgQGAygeaOSG+L1lwF83vRLojmIECAAIECBVbMi/niePyJec95SIAAgS4EXopOPxztrmj3RjsW7Xg0BwECBAgQIPAVgTXxZUe0N0W7PtqmaA4CBNoV+GR019zt00GgN4FVvY1kIAIECJwq0CxRuuZEO/UVjwgQIECAAAECBAgQIFCpgKVJlSbWtAgQIECAAAECBAgQIECAAIH8BBRi8suJiAgQIECAAAECBAgQIECAAIFKBRRiKk2saREgQIAAAQIECBAgQIAAAQL5CSjE5JcTEREgQIAAAQIECBAgQIAAAQKVCijEVJpY0yJAgAABAgQIECBAgAABAgTyE1CIyS8nIiJAgAABAgQIECBAgAABAgQqFVCIqTSxpkWAAAECBAgQIECAAAECBAjkJ6AQk19ORESAAAECBAgQIECAAAECBAhUKqAQU2liTYsAAQIECBAgQIAAAQIECBDIT0AhJr+ciIgAAQIECBAgQIAAAQIECBCoVEAhptLEmhYBAgQIECBAgAABAgQIECCQn4BCTH45EREBAgQIECBAgAABAgQIECBQqYBCTKWJNS0CBAgQIECAAAECBAgQIEAgPwGFmPxyIiICBAgQIECAAAECBAgQIECgUgGFmEoTa1oECBAgQIAAAQIECBAgQIBAfgIKMfnlREQECBAgQIAAAQIECBAgQIBApQIKMZUm1rQIECBAgAABAgQIECBAgACB/AQUYvLLiYgIECBAgAABAgQIECBAgACBSgUUYipNrGkRIECAAAECBAgQIECAAAEC+QkoxOSXExERIECAAAECBAgQIECAAAEClQooxFSaWNMiQIAAAQIECBAgQIAAAQIE8hNQiMkvJyIiQIAAAQIECBAgQIAAAQIEKhVQiKk0saZFgAABAgQIECBAgAABAgQI5CegEJNfTkREgAABAgQIECBAgAABAgQIVCqgEFNpYk2LAAECBAgQIECAAAECBAgQyE9AISa/nIiIAAECBAgQIECAAAECBAgQqFRAIabSxJoWAQIECBAgQIAAAQIECBAgkJ+AQkx+ORERAQIECBAgQIAAAQIECBAgUKmAQkyliTUtAgQIECBAgAABAgQIECBAID8BhZj8ciIiAgQIECBAgAABAgQIECBAoFIBhZhKE2taBAgQIECAAAECBAgQIECAQH4CCjH55UREBAgQIECAAAECBAgQIECAQKUCCjGVJta0CBAgQIAAAQIECBAgQIAAgfwEFGLyy4mICBAgQIAAAQIECBAgQIAAgUoFFGIqTaxpESBAgAABAgQIECBAgAABAvkJKMTklxMRESBAgAABAgQIECBAgAABApUKKMRUmljTIkCAAAECBAgQIECAAAECBPITUIjJLyciIkCAAAECBAgQIECAAAECBCoVUIipNLGmRYAAAQIECBAgQIAAAQIECOQnoBCTX05ERIAAAQIECBAgQIAAAQIECFQqoBBTaWJNiwABAgQIECBAgAABAgQIEMhPQCEmv5yIiAABAgQIECBAgAABAgQIEKhUQCGm0sSaFgECBAgQIECAAAECBAgQIJCfgEJMfjkREQECBAgQIECAAAECBAgQIFCpgEJMpYk1LQIECBAgQIAAAQIECBAgQCA/AYWY/HIiIgIECBAgQIAAAQIECBAgQKBSAYWYShNrWgQIECBAgAABAgQIECBAgEB+Agox+eVERAQIECBAgAABAgQIECBAgEClAgoxlSbWtAgQIECAAAECBAgQIECAAIH8BBRi8suJiAgQIECAAAECBAgQIECAAIFKBRRiKk2saREgQIAAAQIECBAgQIAAAQL5CSjE5JcTEREgQIAAAQIECBAgQIAAAQKVCijEVJpY0yJAgAABAgQIECBAgAABAgTyE1CIyS8nIiJAgAABAgQIECBAgAABAgQqFVCIqTSxpkWAAAECBAgQIECAAAECBAjkJ6AQk19ORESAAAECBAgQIECAAAECBAhUKqAQU2liTYsAAQIECBAgQIAAAQIECBDIT0AhJr+ciIgAAQIECBAgQIAAAQIECBCoVEAhptLEmhYBAgQIECBAgAABAgQIECCQn4BCTH45EREBAgQIECBAgAABAgQIECBQqYBCTKWJNS0CBAgQIECAAAECBAgQIEAgPwGFmPxyIiICBAgQIECAAAECBAgQIECgUgGFmEoTa1oECBAgQIAAAQIECBAgQIBAfgIKMfnlREQECBAgQIAAAQIECBAgQIBApQIKMZUm1rQIECBAgAABAgQIECBAgACB/AQUYvLLiYgIECBAgAABAgQIECBAgACBSgUUYipNrGkRIECAAAECBAgQIECAAAEC+Qmsyi8kEREgMBKBO2Oe74v2sWj3RXsmmoMAAQIECBB4VWBNfLsj2hujHYn21mjrojkIECBAoGABhZiCkyd0AgUKvBQx/7NoPx3tswXGL2QCBAgQIDCUwE/FwFuifVe0H4m2M5qDAAECBAoUsDSpwKQJmUChAp+OuK+K9j3RFGEKTaKwCRAgQGBQgcdj9PdEuzDarw0aicEJECBAYGYBhZiZ6ZxIgMAUAv8x3nt9tGYZkoMAAQIECBBYnsBjcfp3RPvRaMeX15WzCRAgQKBvAUuT+hY3HoHxCfx/MeW3RXtxfFM3YwIECBAg0KnAT0bvL0Rrli05CBAgQKAQAVfEFJIoYRIoVOCeiPuboynCFJpAYRMgQIBA9gLNvmvvzT5KARIgQIDAKwIKMa9Q+IYAgQ4E3hl9PtJBv7okQIAAAQIEXhX4b+LbL7760HcECBAgkLOAQkzO2REbgbIFfivC//2ypyB6AgQIECBQhMBTEeXfLSJSQRIgQIBAUojxISBAoCuBf9RVx/olQIAAAQIEThN4bzzz6GnPeoIAAQIEshNQiMkuJQIiUIXAwzGL361iJiZBgAABAgTKEHguwvw3ZYQqSgIECIxbQCFm3Pk3ewJdCfxhdPxyV53rlwABAgQIEFhQwJLgBVk8SYAAgbwEFGLyyodoCNQi8MlaJmIeBAgQIECgIAE/fwtKllAJEBivgELMeHNv5gS6FHioy871TYAAAQIECCwo4OfvgiyeJECAQF4CCjF55UM0BGoReLaWiZgHAQIECBAoSMDP34KSJVQCBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOQECBAgQIECAAAECBAgQINCzgEJMz+CGI0CAAAECBAgQIECAAAECBMYroBAz3tybOYEuBdZ02bm+CRAgQIAAgQUF/PxdkMWTBAgQyEtAISavfIiGQC0CO2qZiHkQIECAAIGCBPz8LShZQiVAYLwCCjHjzb2ZE+hS4E1ddq5vAgQIECBAYEEBP38XZPEkAQIE8hJQiMkrH6IhUIvATbVMxDwIECBAgEBBAkcKilWoBAgQGK2AQsxoU2/iBDoV2Bu9H+p0BJ0TIECAAAECJwusjAffcPITvidAgACBPAUUYvLMi6gI1CDwfTVMwhwIECBAgEAh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7Q7IT4AAAQIECBAgQIAAAQIECKQRMIhJ02qFEiBAgAABAgQIECBAgAABArUFDGJqd0B+AgQIECBAgAABAgQIECBAII2AQUyaViuUAAECBAgQIECAAAECBAgQqC1gEFO7A/ITIECAAAECBAgQIECAAAECaQQMYtK0WqEECBAgQIAAAQIECBAgQIBAbQGDmNodkJ8AAQIECBAgQIAAAQIECBBII2AQk6bVCiVAgAABAgQIECBAgAABAgRqCxjE1O6A/AQIECBAgAABAgQIECBAgEAaAYOYNK1WKAECBAgQIECAAAECBAgQIFBbwCCmdgfkJ0CAAAECBAgQIECAAAECBNIIGMSkabVCCRAgQIAAAQIECBAgQIAAgdoCBjG1OyA/AQIECBAgQIAAAQIECBAgkEbAICZNqxVKgAABAgQIECBAgAABAgQI1BYwiKndAfkJECBAgAABAgQIECBAgACBNAIGMWlarVACBAgQIECAAAECBAgQIECgtoBBTO0OyE+AAAECBAgQIECAAAECBAikETCISdNqhRIgQIAAAQIECBAgQIAAAQK1BQxiandAfgIECBAgQIAAAQIECBAgQCCNgEFMmlYrlAABAgQIECBAgAABAgQIEKgtYBBTuwPyEyBAgAABAgQIECBAgAABAmkEDGLStFqhBAgQIECAAAECBAgQIECAQG0Bg5jaHZCfAAECBAgQIECAAAECBAgQSCNgEJOm1QolQIAAAQIECBAgQIAAAQIEagsYxNTugPwECBAgQIAAAQIECBAgQIBAGgGDmDStVigBAgQIECBAgAABAgQIECBQW8AgpnYH5CdAgAABAgQIECBAgAABAgTSCBjEpGm1QgkQIECAAAECBAgQIECAAIHaAgYxtTsgPwECBAgQIECAAAECBAgQIJBGwCAmTasVSoAAAQIECBAgQIAAAQIECNQWMIip3QH5CRAgQIAAAQIECBAgQIAAgTQCBjFpWq1QAgQIECBAgAABAgQIECBAoLaAQUztDshPgAABAgQIECBAgAABAgQIpBEwiEnTaoUSIECAAAECBAgQIECAAAECtQUMYmp3QH4CBAgQIECAAAECBAgQIEAgjYBBTJpWK5QAAQIECBAgQIAAAQIECBCoLWAQU7sD8hMgQIAAAQIECBAgQIAAAQJpBAxi0rRaoQQIECBAgAABAgQIECBAgEBtAYOY2h2QnwABAgQIECBAgAABAgQIEEgjYBCTptUKJUCAAAECBAgQIECAAAECBGoLGMTU7oD8BAgQIECAAAECBAgQIECAQBoBg5g0rVYoAQIECBAgQIAAAQIECBAgUFvAIKZ2B+QnQIAAAQIECBAgQIAAAQIE0ggYxKRptUIJECBAgAABAgQIECBAgACB2gIGMbU7ID8BAgQIECBAgAABAgQIECCQRsAgJk2rFUqAAAECBAgQIECAAAECBAjUFjCIqd0B+QkQIECAAAECBAgQIECAAIE0AgYxaVqtUAIECBAgQIAAAQIECBAgQKC2gEFM7Q7IT4AAAQIECBAgQIAAAQIECKQRMIhJ02qFEiBAgAABAgQIECBAgAABArUFDGJqd0B+AgQIECBAgAABAgQIECBAII2AQUyaViuUAAECBAgQIECAAAECBAgQqC1gEFO7A/ITIECAAAECBAgQIECAAAECaQQMYtK0WqEECBAgQIAAAQIECBAgQIBAbQGDmNodkJ8AAQIECBAgQIAAAQIECBBII2AQk6bVCiVAgAABAgQIECBAgAABAgRqCxjE1O6A/AQIECBAgAABAgQIECBAgEAaAYOYNK1WKAECBAgQIECAAAECBAgQIFBbwCCmdgfkJ0CAAAECBAgQIECAAAECBNIIGMSkabVCCRAgQIAAAQIECBAgQIAAgdoCBjG1OyA/AQIECBAgQIAAAQIECBAgkEbAICZNqxVKgAABAgQIECBAgAABAgQI1BYwiKndAfkJECBAgAABAgQIECBAgACBNAIGMWlarVACBAgQIECAAAECBAgQIECgtoBBTO0OyE+AAAECBAgQIECAAAECBAikETCISdNqhRIgQIAAAQIECBAgQIAAAQK1BQxiandAfgIECBAgQIAAAQIECBAgQCCNgEFMmlYrlAABAgQIECBAgAABAgQIEKgtYBBTuwPyEyBAgAABAgQIECBAgAABAmkEDGLStFqhBAgQIECAAAECBAgQIECAQG0Bg5jaHZCfAAECBAgQIECAAAECBAgQSCNgEJOm1QolQIAAAQIECBAgQIAAAQIEagsYxNTugPwECBAgQIAAAQIECBAgQIBAGgGDmDStVigBAgQIECBAgAABAgQIECBQW8AgpnYH5CdAgAABAgQIECBAgAABAgTSCBjEpGm1QgkQIECAAAECBAgQIECAAIHaAgYxtTsgPwECBAgQIECAAAECBAgQIJBGwCAmTasVSoAAAQIECBAgQIAAAQIECNQWMIip3QH5CRAgQIAAAQIECBAgQIAAgTQCBjFpWq1QAgQIECBAgAABAgQIECBAoLaAQUztDshPgAABAgQIECBAgAABAgQIpBEwiEnTaoUSIECAAAECBAgQIECAAAECtQUMYmp3QH4CBAgQIECAAAECBAgQIEAgjYBBTJpWK5QAAQIECBAgQIAAAQIECBCoLWAQU7sD8hMgQIAAAQIECBAgQIAAAQJpBAxi0rRaoQQIECBAgAABAgQIECBAgEBtAYOY2h2QnwABAgQIECBAgAABAgQIEEgjYBCTptUKJUCAAAECBAgQIECAAAECBGoLGMTU7oD8BAgQIECAAAECBAgQIECAQBoBg5g0rVYoAQIECBAgQIAAAQIECBAgUFvAIKZ2B+QnQIAAAQIECBAgQIAAAQIE0ggYxKRptUIJECBAgAABAgQIECBAgACB2gIGMbU7ID8BAgQIECBAgAABAgQIECCQRsAgJk2rFUqAAAECBAgQIECAAAECBAjUFjCIqd0B+QkQIECAAAECBAgQIECAAIE0AgYxaVqtUAIECBAgQIAAAQIECBAgQKC2gEFM7Q7IT4AAAQIECBAgQIAAAQIECKQRMIhJ02qFEiBAgAABAgQIECBAgAABArUFDGJqd0B+AgQIECBAgAABAgQIECBAII2AQUyaViuUAAECBAgQIECAAAECBAgQqC1gEFO7A/ITIECAAAECBAgQIECAAAECaQQMYtK0WqEECBAgQIAAAQIECBAgQIBAbQGDmNodkJ8AAQIECBAgQIAAAQIECBBII2AQk6bVCiVAgAABAgQIECBAgAABAgRqCxjE1O6A/AQIECBAgAABAgQIECBAgEAaAYOYNK1WKAECBAgQIECAAAECBAgQIFBbwCCmdgfkJ0CAAAECBAgQIECAAAECBNIIGMSkabVCCRAgQIAAAQIECBAgQIAAgdoCBjG1OyA/AQIECBAgQIAAAQIECBAgkEbAICZNqxVKgAABAgQIECBAgAABAgQI1BYwiKndAfkJECBAgAABAgQIECBAgACBNAIGMWlarVACBAgQIECAAAECBAgQIECgtoBBTO0OyE+AAAECBAgQIECAAAECBAikETCISdNqhRIgQIAAAQIECBAgQIAAAQK1BQxiandAfgIECBAgQIAAAQIECBAgQCCNgEFMmlYrlAABAgQIECBAgAABAgQIEKgtYBBTuwPyEyBAgAABAgQIECBAgAABAmkEDGLStFqhBAgQIECAAAECBAgQIECAQG0Bg5jaHZCfAAECBAgQIECAAAECBAgQSCNgEJOm1QolQIAAAQIECBAgQIAAAQIEagsYxNTugPwECBAgQIAAAQIECBAgQIBAGgGDmDStVigBAgQIECBAgAABAgQIECBQW8AgpnYH5CdAgAABAgQIECBAgAABAgTSCBjEpGm1QgkQIECAAAECBAgQIECAAIHaAgYxtTsgPwECBAgQIECAAAECBAgQIJBGwCAmTasVSoAAAQIECBAgQIAAAQIECNQWMIip3QH5CRAgQIAAAQIECBAgQIAAgTQCBjFpWq1QAgQIECBAgAABAgQIECBAoLaAQUztDshPgAABAgQIECBAgAABAgQIpBEwiEnTaoUSIECAAAECBAgQIECAAAECtQUMYmp3QH4CBAgQIECAAAECBAgQIEAgjYBBTJpWK5QAAQIECBAgQIAAAQIECBCoLWAQU7sD8hMgQIAAAQIECBAgQIAAAQJpBAxi0rRaoQQIECBAgAABAgQIECBAgEBtAYOY2h2QnwABAgQIECBAgAABAgQIEEgjYBCTptUKJUCAAAECBAgQIECAAAECBGoLGMTU7oD8BAgQIECAAAECBAgQIECAQBoBg5g0rVYoAQIECBAgQIAAAQIECBAgUFvAIKZ2B+QnQIAAAQIECBAgQIAAAQIE0ggYxKRptUIJECBAgAABAgQIECBAgACB2gIGMbU7ID8BAgQIECBAgAABAgQIECCQRsAgJk2rFUqAAAECBAgQIECAAAECBAjUFjCIqd0B+QkQIECAAAECBAgQIECAAIE0AgYxaVqtUAIECBAgQIAAAQIECBAgQKC2gEFM7Q7IT4AAAQIECBAgQIAAAQIECKQRMIhJ02qFEiBAgAABAgQIECBAgAABArUFDGJqd0B+AgQIECBAgAABAgQIECBAII2AQUyaViuUAAECBAgQIECAAAECBAgQqC1gEFO7A/ITIECAAAECBAgQIECAAAECaQQMYtK0WqEECBAgQIAAAQIECBAgQIBAbQGDmNodkJ8AAQIECBAgQIAAAQIECBBII2AQk6bVCiVAgAABAgQIECBAgAABAgRqCxjE1O6A/AQIECBAgAABAgQIECBAgEAaAYOYNK1WKAECBAgQIECAAAECBAgQIFBbwCCmdgfkJ0CAAAECBAgQIECAAAECBNIIGMSkabVCCRAgQIAAAQIECBAgQIAAgdoCBjG1OyA/AQIECBAgQIAAAQIECBAgkEbAICZNqxVKgAABAgQIECBAgAABAgQI1BYwiKndAfkJECBAgAABAgQIECBAgACBNAIGMWlarVACBAgQIECAAAECBAgQIECgtoBBTO0OyE+AAAECBAgQIECAAAECBAikETCISdNqhRIgQIAAAQIECBAgQIAAAQK1BQxiandAfgIECBAgQIAAAQIECBAgQCCNgEFMmlYrlAABAgQIECBAgAABAgQIEKgtYBBTuwPyEyBAgAABAgQIECBAgAABAmkEDGLStFqhBAgQIECAAAECBAgQIECAQG0Bg5jaHZCfAAECBAgQIECAAAECBAgQSCNgEJOm1QolQIAAAQIECBAgQIAAAQIEagsYxNTugPwECBAgQIAAAQIECBAgQIBAGgGDmDStVigBAgQIECBAgAABAgQIECBQW8AgpnYH5CdAgAABAgQIECBAgAABAgTSCBjEpGm1QgkQIECAAAECBAgQIECAAIHaAgYxtTsgPwECBAgQIECAAAECBAgQIJBGwCAmTasVSoAAAQIECBAgQIAAAQIECNQWMIip3QH5CRAgQIAAAQIECBAgQIAAgTQCBjFpWq1QAgQIECBAgAABAgQIECBAoLaAQUztDshPgAABAgQIECBAgAABAgQIpBEwiEnTaoUSIECAAAECBAgQIECAAAECtQUMYmp3QH4CBAgQIECAAAECBAgQIEAgjYBBTJpWK5QAAQIECBAgQIAAAQIECBCoLWAQU7sD8hMgQIAAAQIECBAgQIAAAQJpBAxi0rRaoQQIECBAgAABAgQIECBAgEBtAYOY2h2QnwABAgQIECBAgAABAgQIEEgjYBCTptUKJUCAAAECBAgQIECAAAECBGoLGMTU7oD8BAgQIECAAAECBAgQIECAQBoBg5g0rVYoAQIECBAgQIAAAQIECBAgUFvAIKZ2B+QnQIAAAQIECBAgQIAAAQIE0ggYxKRptUIJECBAgAABAgQIECBAgACB2gIGMbU7ID8BAgQIECBAgAABAgQIECCQRsAgJk2rFUqAAAECBAgQIECAAAECBAjUFjCI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')
                        .css({
                            'width': '16px',
                            'height': '16px',
                            'vertical-align': 'middle',
                            'filter': 'brightness(0) invert(1)' // Make the SVG white to match button text
                        }))
                    .css({
                        'margin-left': '1px',
                        'align-items': 'center',
                        'transform': 'translateY(2px)',
                        'padding': '2px 8px',
                        'background-color': 'rgba(46, 204, 113, 0.0)',
                        'color': 'white',
                        'border': 'none',
                        'border-radius': '3px',
                        'cursor': 'pointer',
                        'display': 'inline-flex',
                        'align-items': 'center'
                })
                .click(function(e) {
                    e.stopPropagation();  // Prevent row click
                    pycmd('train:' + deckId);
                });
                
            // Add the button after the deck name
            $deckLink.after($button);
        }
    });
}, 100);
"""
    mw.deckBrowser.web.eval(js)
       



# Global message counter
message_count = 0


def handle_bridge_cmd(message):
    """Handle bridge commands from JavaScript."""
    global message_count
    message_count += 1
    loading_dialog = None
    
    if isinstance(message, str):
        if message.startswith("anki_exam_debug:"):
            debug_msg = message.split(":", 1)[1]
            return True
        elif message.startswith("train:"):
            # Extract deck ID
            deck_id = message.split(":", 1)[1]
            #showInfo(f"DEBUG #{message_count}: Training deck ID {deck_id}", parent=mw)
            try:
                # Create modal loading dialog with animated GIF
                loading_dialog = QDialog(mw)
                loading_dialog.setWindowModality(Qt.WindowModality.ApplicationModal)
                # Frameless, transparent, always on top
                loading_dialog.setWindowFlags(
                    Qt.WindowType.FramelessWindowHint
                    | Qt.WindowType.Tool
                    | Qt.WindowType.WindowStaysOnTopHint
                )
                loading_dialog.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

                vbox = QVBoxLayout()
                vbox.setAlignment(Qt.AlignmentFlag.AlignCenter)
                vbox.setContentsMargins(0, 0, 0, 0)
                vbox.setSpacing(0)

                gif_label = QLabel()
                gif_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                # Try to build an animation from a series of images: img1..img8
                import os
                addon_dir = os.path.dirname(__file__)
                icons_dir = os.path.join(addon_dir, "icons")
                series_dir = os.path.join(icons_dir, "Loading_gifs")

                frames = []
                if os.path.isdir(series_dir):
                    for i in range(1, 9):
                        found = False
                        for ext in ("png", "jpg", "jpeg", "gif", "webp"):
                            p = os.path.join(series_dir, f"img{i}.{ext}")
                            if os.path.exists(p):
                                frames.append(QPixmap(p))
                                found = True
                                break
                        if not found:
                            # allow zero-padded like img01
                            for ext in ("png", "jpg", "jpeg", "gif", "webp"):
                                p = os.path.join(series_dir, f"img0{i}.{ext}")
                                if os.path.exists(p):
                                    frames.append(QPixmap(p))
                                    break

                if frames:
                    # Set initial frame and start a timer to animate (smaller icon)
                    target_size = 32
                    gif_label.setFixedSize(target_size, target_size)
                    gif_label.setPixmap(frames[0].scaled(target_size, target_size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

                    timer = QTimer(loading_dialog)
                    timer.setInterval(120)
                    loading_dialog._frames = frames
                    loading_dialog._frame_index = 0
                    loading_dialog._timer = timer
                    loading_dialog._gif_label = gif_label

                    def advance_frame():
                        if not loading_dialog.isVisible():
                            return
                        loading_dialog._frame_index = (loading_dialog._frame_index + 1) % len(loading_dialog._frames)
                        pix = loading_dialog._frames[loading_dialog._frame_index].scaled(
                            target_size,
                            target_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        loading_dialog._gif_label.setPixmap(pix)

                    timer.timeout.connect(advance_frame)
                    timer.start()
                else:
                    # Fallback to a standalone GIF if present, else text
                    gif_candidates = [
                        os.path.join(series_dir, "loading.gif"),
                        os.path.join(series_dir, "spinner.gif"),
                        os.path.join(series_dir, "dots.gif"),
                    ]
                    movie = None
                    for path in gif_candidates:
                        if os.path.exists(path):
                            movie = QMovie(path)
                            break
                    if movie is not None:
                        gif_label.setMovie(movie)
                        movie.start()
                    else:
                        gif_label.setText("Loading…")

                vbox.addWidget(gif_label)
                loading_dialog.setLayout(vbox)
                # Size dialog tightly around the icon
                loading_dialog.adjustSize()
                loading_dialog.setFixedSize(gif_label.width(), gif_label.height())
                # Center over main window
                try:
                    parent_geom = mw.frameGeometry()
                    center_pt = parent_geom.center()
                    x = center_pt.x() - loading_dialog.width() // 2
                    y = center_pt.y() - loading_dialog.height() // 2
                    loading_dialog.move(x, y)
                except Exception:
                    pass

                loading_dialog.show()
                loading_dialog.raise_()
                loading_dialog.activateWindow()
                QApplication.processEvents()

                # Run the long task
                train_from_deck(deck_id)
            finally:
                # Always close the loading dialog
                if loading_dialog is not None:
                    try:
                        if hasattr(loading_dialog, "_timer"):
                            loading_dialog._timer.stop()
                        loading_dialog.close()
                    except Exception:
                        pass
            return True
    return False

# Global cooldown variables
message_cooldown = 5  # 5 second cooldown
last_message_time = 0

def handle_webview_message(handled, message, context):
    """Handle messages specifically for our addon with cooldown."""
    global last_message_time
    
    # Check if we're still in cooldown
    current_time = time.time()
    if current_time - last_message_time < message_cooldown:
        #showInfo(f"DEBUG: Cooldown active - ignoring message", parent=mw)
        return (False, None)
    
    # Only handle messages from our addon
    if not isinstance(message, str):
        return (False, None)
    
    # Check if this is our addon's message
    if not message.startswith('train:') and not message.startswith('anki_exam_debug:'):
        return (False, None)
    
    # Handle the message
    if handle_bridge_cmd(message):
        # Update last message time when handling a message
        last_message_time = current_time
        return (True, None)
    
    return (False, None)

# Add hooks
gui_hooks.deck_browser_did_render.append(inject_train_buttons)

# Uncomment the webview message handler
#showInfo("Registering webview message handler", parent=mw)
gui_hooks.webview_did_receive_js_message.append(handle_webview_message)