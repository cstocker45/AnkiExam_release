from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import *
from anki.notes import Note
from . import AnkiExamCard
from .shared import credential_manager, questions_cycle
from . import ClientAuth
from PyQt6.QtCore import QThread, pyqtSignal, QPropertyAnimation, QEasingCurve, QEvent, QObject, QTimer
from PyQt6.QtGui import QIcon, QScreen, QColor
from PyQt6.QtWidgets import QGraphicsDropShadowEffect
from PyQt6.QtCore import Qt, QSize
import os
import uuid
import re
from datetime import datetime
import time
from .models import uploaded_txt_content, QuestionWorker
from aqt import gui_hooks




#Main selection window to all for various AnkiExam tools
# ...existing imports...

#initialize uploaded pdf content
uploaded_txt_content = {"content": ""}

# Import questions_cycle from shared instead of redefining it
from .shared import questions_cycle

DEBUG = False
#Integration of login box for authentication
auth_client = ClientAuth.AuthClient()

#Create the login box for authentication.
def prompt_for_login():
    dlg = QDialog(mw)
    dlg.setWindowTitle("Login to AnkiExam Server")
    layout = QVBoxLayout()
    user_label = QLabel("Username:")
    user_input = QLineEdit()
    pass_label = QLabel("Password:")
    pass_input = QLineEdit()
    pass_input.setEchoMode(QLineEdit.EchoMode.Password)
    email_label = QLabel("Email:")
    email_input = QLineEdit()
    # Get MAC address automatically
    mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])

    login_btn = QPushButton("Login")
    register_btn = QPushButton("Register")
    status_label = QLabel("")
    layout.addWidget(user_label)
    layout.addWidget(user_input)
    layout.addWidget(pass_label)
    layout.addWidget(pass_input)
    layout.addWidget(email_label)
    layout.addWidget(email_input)
    layout.addWidget(login_btn)
    layout.addWidget(register_btn)
    layout.addWidget(status_label)
    dlg.setLayout(layout)
    dlg.setMinimumWidth(300)

    def do_login():
        username = user_input.text().strip()
        password = pass_input.text().strip()
        if not username or not password:
            status_label.setText("Please enter both username and password.")
            status_label.setStyleSheet("color: red;")
            return
        if auth_client.login(username, password):
            dlg.accept()
        else:
            status_label.setText("Login failed. Try again.")

    login_btn.clicked.connect(do_login)

    def do_register():
        username = user_input.text().strip()
        password = pass_input.text().strip()
        email = email_input.text().strip()
        if not username or not password or not email:
            status_label.setText("Please enter username, password, and email.")
            status_label.setStyleSheet("color: red;")
            return
        success, msg = auth_client.register(username, password, email, mac_address)
        status_label.setText(str(msg))
        if success:
            status_label.setStyleSheet("color: green;")
            verify_dlg = show_verification_dialog(username)
            if verify_dlg:  # If verification was successful
                do_login()  # Attempt to log in automatically
        else:
            status_label.setStyleSheet("color: red;")

    register_btn.clicked.connect(do_register)
    dlg.exec()

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

def get_icon_path(icon_name):
    """Get the absolute path to an icon file"""
    return os.path.join(os.path.dirname(__file__), 'icons', icon_name)

#Main selection window to all for various AnkiExam tools
def selection_window_gui():
    # Get the primary screen and set default dimensions
    window_width = 1024  # Default width
    window_height = 768  # Default height
    
    screen = QApplication.primaryScreen()
    if screen:
        screen_geometry = screen.geometry()
        # Calculate 70% of screen dimensions
        window_width = int(screen_geometry.width() * 0.7)
        window_height = int(screen_geometry.height() * 0.7)

    dlg = QDialog(mw)
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
            border: 1px solid #455d7a;
            width: 180px;  /* Fixed width for input fields */
        }
        QLineEdit:focus {
            border: 1px solid #74b9ff;
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

    # Login form fields
    user_input = QLineEdit()
    user_input.setPlaceholderText("Username")
    pass_input = QLineEdit()
    pass_input.setPlaceholderText("Password")
    pass_input.setEchoMode(QLineEdit.EchoMode.Password)
    email_input = QLineEdit()
    email_input.setPlaceholderText("Email (for registration)")
    remember_checkbox = QCheckBox("Remember me")

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
        layout_bg.setStyleSheet("background-color: #34495e; border: none;")  # Bright green
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
            }
            QPushButton {
                border: none;
                background-color: transparent;
                padding: 10px;
            }
        """)
        
        # Make sure the container accepts hover events
        container.setAttribute(Qt.WidgetAttribute.WA_Hover)
        btn.setAttribute(Qt.WidgetAttribute.WA_Hover)
        
        return container

    def do_login():
        username = user_input.text().strip()
        password = pass_input.text().strip()
        if not username or not password:
            status_label.setText("Please enter both username and password.")
            return
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

    def do_register():
        username = user_input.text().strip()
        password = pass_input.text().strip()
        email = email_input.text().strip()
        if not username or not password or not email:
            status_label.setText("Please enter username, password, and email.")
            return
        # Get MAC address automatically
        mac_address = ':'.join(['{:02x}'.format((uuid.getnode() >> ele) & 0xff) for ele in range(0,8*6,8)][::-1])
        success, msg = auth_client.register(username, password, email, mac_address)
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
            }
        """)
        layout.addWidget(text_input)
        
        # Add train button
        train_btn = QPushButton("Generate Questions")
        train_btn.setFixedWidth(200)
        train_btn.setStyleSheet("""
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
        btn_layout.addWidget(train_btn)
        btn_container.setLayout(btn_layout)
        layout.addWidget(btn_container)

        def on_upload():
            file_path, _ = QFileDialog.getOpenFileName(None, "Select File", "", "All Supported Files (*.txt *.pdf);;Text Files (*.txt);;PDF Files (*.pdf)")
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
            train_btn.setEnabled(False)
            train_btn.setText("Generating...")
            
            # Show loading indicator
            progress = QProgressBar()
            progress.setRange(0, 0)
            layout.addWidget(progress)
            
            try:
                train_model_on_text(text_input.toPlainText())
                progress.hide()
                train_btn.setEnabled(True)
                train_btn.setText("Generate Questions")
                create_question_content(content_area)
            except Exception as e:
                progress.hide()
                train_btn.setEnabled(True)
                train_btn.setText("Generate Questions")
                showInfo(f"Error: {str(e)}")
        
        upload_btn.clicked.connect(on_upload)
        use_deck_btn.clicked.connect(on_use_deck)
        train_btn.clicked.connect(on_train)

    def create_question_content(content_area):
        # Clear existing content
        for i in reversed(range(content_area.layout().count())): 
            content_area.layout().itemAt(i).widget().setVisible(False)
            content_area.layout().itemAt(i).widget().deleteLater()
            
        layout = content_area.layout()
        
        from .pdf_training import questions_cycle
        questions = questions_cycle["questions"]
        idx = questions_cycle["index"]
        
        if not questions or idx >= len(questions):
            # Show no questions message
            msg = QLabel("No questions available.\nPlease input training data first.")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet("""
                font-size: 18px;
                color: #2d3436;
                margin: 20px;
            """)
            layout.addWidget(msg)
            return
            
        question = questions[idx]
        
        # Add question label
        question_label = QLabel("Please answer the following question:")
        question_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question_label.setStyleSheet("""
            font-size: 18px;
            color: #2d3436;
            margin: 20px;
        """)
        layout.addWidget(question_label)
        
        # Add the actual question
        question_text = QLabel(question)
        question_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        question_text.setWordWrap(True)
        question_text.setStyleSheet("""
            font-size: 24px;
            color: #2d3436;
            margin: 20px;
            font-weight: bold;
        """)
        layout.addWidget(question_text)
        
        # Add answer input
        answer_input = QLineEdit()
        answer_input.setPlaceholderText("Type your answer here...")
        answer_input.setFixedHeight(40)
        answer_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #dfe6e9;
                border-radius: 4px;
                padding: 10px;
                font-size: 16px;
                background-color: white;
                margin: 20px;
            }
        """)
        layout.addWidget(answer_input)
        
        # Add submit button
        submit_btn = QPushButton("Submit Answer")
        submit_btn.setFixedWidth(200)
        submit_btn.setStyleSheet("""
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
        btn_layout.addWidget(submit_btn)
        btn_container.setLayout(btn_layout)
        layout.addWidget(btn_container)
        
        def on_submit():
            if not answer_input.text().strip():
                showInfo("Please enter an answer.")
                return
                
            submit_btn.setEnabled(False)
            submit_btn.setText("Checking...")
            
            # Show loading indicator
            progress = QProgressBar()
            progress.setRange(0, 0)
            layout.addWidget(progress)
            
            # Create worker to handle answer checking
            worker = AnswerWorker(answer_input.text(), question)
            
            def on_finished(output, total_tokens):
                progress.hide()
                
                # Show result
                result_label = QLabel(f"Feedback:\n{output}\n\nTokens used: {total_tokens}")
                result_label.setWordWrap(True)
                result_label.setStyleSheet("""
                    font-size: 16px;
                    color: #2d3436;
                    margin: 20px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    border-radius: 4px;
                """)
                layout.addWidget(result_label)
                
                # Add next question button if available
                questions_cycle["index"] += 1
                if questions_cycle["index"] < len(questions_cycle["questions"]):
                    next_btn = QPushButton("Next Question")
                    next_btn.setFixedWidth(200)
                    next_btn.setStyleSheet("""
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
                    next_btn.clicked.connect(lambda: create_question_content(content_area))
                    
                    btn_container = QWidget()
                    btn_layout = QHBoxLayout()
                    btn_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    btn_layout.addWidget(next_btn)
                    btn_container.setLayout(btn_layout)
                    layout.addWidget(btn_container)
                else:
                    done_label = QLabel("You have completed all questions!")
                    done_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    done_label.setStyleSheet("""
                        font-size: 18px;
                        color: #2d3436;
                        
                        margin: 20px;
                    """)
                    layout.addWidget(done_label)
            
            def on_error(error_msg):
                progress.hide()
                submit_btn.setEnabled(True)
                submit_btn.setText("Submit Answer")
                showInfo(f"Error: {error_msg}")
            
            worker.finished.connect(on_finished)
            worker.error.connect(on_error)
            worker.start()
        
        submit_btn.clicked.connect(on_submit)

    def on_training():
        create_training_content(content_area)

    def on_question():
        create_question_content(content_area)

    # Connect buttons to their functions
    login_btn.clicked.connect(do_login)
    register_btn.clicked.connect(do_register)

    # Create tool buttons
    training_btn = create_sidebar_button(
        "book.png",
        "Input Training Data",
        on_training
    )
    
    question_btn = create_sidebar_button(
        "question.png",
        "Input Question",
        on_question
    )
    
    logout_btn = create_sidebar_button(
        "logout.png",
        "Logout",
        do_logout
    )

    # Add buttons to tools section
    tools_layout.addWidget(training_btn)
    tools_layout.addWidget(question_btn)
    tools_layout.addStretch()  # Push logout to bottom
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

    # Welcome message in content area
    welcome_label = QLabel("Welcome to AnkiExam Tool!")
    welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    welcome_label.setStyleSheet("""
        font-size: 24px;
        color: #2d3436;
        margin: 20px;
        font-weight: bold;
    """)
    content_layout.addWidget(welcome_label)


    # Try auto-login if we have saved credentials
    saved_creds = credential_manager.load_credentials()
    if saved_creds:
        user_input.setText(saved_creds['username'])
        pass_input.setText(saved_creds['password'])
        remember_checkbox.setChecked(True)
        login_form.hide()
        tools_section.show()
        # Set initial sidebar width based on login state
        sidebar.setFixedWidth(60)
        sidebar_layout.setContentsMargins(1, 20, 1, 20)
    else:
        tools_section.hide()
        login_form.show()
        # Set initial sidebar width based on login state
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

def train_from_deck(deck_name):
    """Train on cards from a specific deck."""
    if not mw.col:
        showInfo("Anki collection not available.")
        return
        
    showInfo(f"Training from deck: {deck_name}")
    # Get all cards from the deck
    card_ids = mw.col.find_cards(f"deck:{deck_name}")
    if not card_ids:
        showInfo("No cards found in deck")
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
    
    # Initialize questions cycle
    questions_cycle["index"] = 0
    questions_cycle["questions"] = []  # We'll populate this later
    
    # Process the deck content
    if uploaded_txt_content["content"]:
        # This would typically be where we generate questions from the content
        # For now, we'll just show a debug message
        showInfo(f"Deck content processed: {uploaded_txt_content['file_name']}")

def inject_train_buttons(*args):
    """Inject a train button next to each deck name in the deck browser."""
    # Only run if we're actually in the deck browser view
    if not mw.state == 'deckBrowser':
        return

    # Only inject if the webview exists
    if not hasattr(mw, 'deckBrowser') or not mw.deckBrowser or not mw.deckBrowser.web:
        return

    js = """
    (function() {
        // Add CSS for the button
        var style = document.createElement('style');
        style.textContent = `
            .train-btn {
                color: white;
                border: none;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                margin-left: 8px;
                cursor: pointer;
                display: inline-block;
                vertical-align: middle;
                transition: background-color 0.3s ease;
            }
            .train-btn:hover {
                background-color: #27ae60;
            }
        `;
        document.head.appendChild(style);

        // Find all deck rows (they have class "deck" and are inside tr elements)
        var deckRows = document.querySelectorAll('tr.deck');
        if (deckRows.length === 0) {
            return;
        }
        
        deckRows.forEach(function(row) {
            // Find the deck name cell (td with class "decktd")
            var nameCell = row.querySelector('td.decktd');
            if (!nameCell) {
                return;
            }
            
            // Find the deck link inside the cell
            var link = nameCell.querySelector('a.deck');
            if (!link) {
                return;
            }
            
            // Check if button already exists
            if (nameCell.querySelector('.train-btn')) {
                return;
            }
            
            // Create train button with initial color
            var btn = document.createElement('button');
            btn.className = 'train-btn';
            btn.textContent = 'Train';
            btn.style.backgroundColor = '#2ecc71'; // Initial green color
            
            // Store the link reference on the button
            btn.dataset.deckLink = link.textContent.trim();
            
            // Add click handler that matches Anki's built-in pattern exactly
            btn.onclick = function() {
                // Change color to orange when clicked
                this.style.backgroundColor = '#e67e22';
                
                // Escape the deck name for the search query
                var deckName = this.dataset.deckLink.replace(/:/g, '\\:')
                        .replace(/\s+/g, ' ')
                        .trim();
                
                // Send the command with escaped name
                pycmd('train:' + deckName);
                
                // Change color to blue while waiting for response
                this.style.backgroundColor = '#3498db';
                
                // Return false to prevent default action
                return false;
            };
            
            // Add event listener for compatibility
            btn.addEventListener('click', function(e) {
                e.preventDefault();
                e.stopPropagation();
                
                // Change color to purple when event listener is triggered
                this.style.backgroundColor = '#9b59b6';
                
                // Call the onclick handler
                var result = this.onclick();
                
                // Change color back to green if onclick returns true
                if (result === true) {
                    this.style.backgroundColor = '#2ecc71';
                }
                
                return result;
            });
            
            // Send debug info to Python side
            pycmd('anki_exam_debug:Button properties: ' + JSON.stringify({
                className: btn.className,
                hasClickHandler: !!btn.onclick,
                clickHandlerType: typeof btn.onclick,
                hasEventListener: btn.closest('tr') ? 'using parent event listener' : 'no parent found',
                eventListeners: btn.addEventListener ? 'supported' : 'not supported'
            }));
            
            // Insert after the link
            link.parentNode.insertBefore(btn, link.nextSibling);
        });
    })();
    
    // Save the HTML after injection
    pycmd('anki_exam_save_html');
    """
    mw.deckBrowser.web.eval(js)
       



# Global message counter
message_count = 0


def handle_bridge_cmd(message):
    """Handle bridge commands from JavaScript."""
    global message_count
    message_count += 1
    
    if isinstance(message, str):
        if message.startswith("anki_exam_debug:"):
            debug_msg = message.split(":", 1)[1]
            #commenting out the anki_exam_debug... at least the debug messages are being sent...
            #showInfo(f"DEBUG #{message_count}: {debug_msg}", parent=mw)
            return True
        elif message.startswith("train:"):
            # Extract and unescape the deck name
            deck_name = message.split(":", 1)[1].replace('\\:', ':')
            showInfo(f"DEBUG #{message_count}: Training deck {deck_name}", parent=mw)
            train_from_deck(deck_name)
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
showInfo("Registering webview message handler", parent=mw)
gui_hooks.webview_did_receive_js_message.append(handle_webview_message)


