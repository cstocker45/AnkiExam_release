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

# Import token history manager
from .token_history import token_history


#Worker thread to handle question generation
from .answer_worker import AnswerWorker
from .webview import inject_train_buttons, handle_bridge_cmd, handle_webview_message
from .widgets import make_button, get_icon_path, PersistentDialog
from .hover import HoverFilter

# Import questions_cycle from shared instead of redefining it
from .shared import questions_cycle

# Initialize status bar with token display
from . import status_bar



# Create a single AuthClient instance to be used throughout the addon
from .ClientAuth import AuthClient
import platform

auth_client = AuthClient()


#initialize uploaded pdf content
uploaded_txt_content = {"content": ""}

DEBUG = False

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

import os

def get_icon_path(icon_name):
    """Get the absolute path to an icon file"""
    return os.path.join(os.path.dirname(__file__), 'icons', icon_name)


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


# make_button and get_icon_path imported from src.ui.widgets

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

    # Use imported PersistentDialog

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
        
        # Apply event filter to both container and button (imported HoverFilter)
        hover_filter = HoverFilter(on_hover_enter, on_hover_leave, container)
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
        # Populate from server-allowed models; fallback to basic free list on error
        api_to_label = {}
        label_to_api = {}
        try:
            #from .src.ClientAuth import AuthClient
            #client = AuthClient()
            if auth_client.is_authenticated():
                resp = auth_client.get_allowed_models()
                models = resp.get("models", [])
                for m in models:
                    label = m.get("label")
                    api = m.get("api")
                    if label and api:
                        model_combo.addItem(label)
                        api_to_label[api] = label
                        label_to_api[label] = api
        except Exception:
            pass
        if model_combo.count() == 0:
            defaults = [
                ("DeepSeek R1 Distill Llama 70B Free", "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"),
                ("Llama 3.3 70B Instruct Turbo Free", "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"),
            ]
            for label, api in defaults:
                model_combo.addItem(label)
                api_to_label[api] = label
                label_to_api[label] = api
        # Reflect current saved selection
        try:
            from .shared import get_model_name
            current_api_model = get_model_name()
            current_label = api_to_label.get(current_api_model, None)
            if not current_label and model_combo.count() > 0:
                current_label = model_combo.itemText(0)
            model_combo.setCurrentText(current_label)
        except Exception:
            if model_combo.count() > 0:
                model_combo.setCurrentIndex(0)

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
            api_model = label_to_api.get(model_name, None)
            if not api_model and model_combo.count() > 0:
                # Fall back to first
                first_label = model_combo.itemText(0)
                api_model = label_to_api.get(first_label)
            # Update the model in shared configuration
            from .shared import update_model
            if api_model:
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

#def inspect_cache():
#    dlg = QDialog(mw)
#    dlg.setWindowTitle("Cache Inspection")
#    from .pdf_training import questions_cycle  # Ensure you use the shared dict
#    questions = questions_cycle["questions"]
#    showInfo(f"Questions: {(questions)}")
#    if not questions:
#        showInfo("No questions in cache!")
#        return
#    dlg.setMinimumWidth(800)
#    dlg.setMinimumHeight(200)
#    dlg.setStyleSheet("background-color: #ff91da; color: white; font-weight: bold; font-size: 16px;")
#    layout = QVBoxLayout()
#    layout.setAlignment(Qt.AlignmentFlag.AlignTop)
#    layout.addWidget(make_button("Close", dlg.accept))
#    dlg.setLayout(layout)
#    dlg.exec()
#



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

# Global message counter
message_count = 0

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


@require_access_key
def train_from_deck(deck_id):
    if not mw.col:
        showInfo("Anki collection not available.")
        return

    try:
        deck_id = str(deck_id)
    except ValueError:
        showInfo(f"Invalid deck ID: {deck_id}")
        return

    deck = mw.col.decks.get(deck_id)
    if not deck:
        showInfo(f"Deck with ID {deck_id} not found")
        return

    deck_name = deck['name']
    card_ids = mw.col.find_cards(f"did:{deck_id}")
    if not card_ids:
        showInfo(f"No cards found in deck '{deck_name}'")
        return

    cards_content = []
    for card_id in card_ids:
        card = mw.col.get_card(card_id)
        note = card.note()
        if note.fields:
            cards_content.append(note.fields[0])

    combined_content = "\n\n".join(cards_content)


    # Get auth_client from the root addon via relative import
    #from . import auth_client
    # Get uploaded_txt_content from models
    #from .src.models import uploaded_txt_content
   
    uploaded_txt_content["content"] = combined_content
    uploaded_txt_content["file_name"] = f"deck_{deck_name}.txt"

    addon_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    content_file = os.path.join(addon_dir, "uploaded_txt_content.txt")
    with open(content_file, "w", encoding="utf-8") as f:
        f.write(combined_content)

    if not auth_client.is_authenticated():
        showInfo("Error: Not authenticated. Please log in again.")
        return

    try:
        usage_before = auth_client.get_token_usage()
        from .pdf_training import train_model_on_text
        from .shared import get_model_name
        
        train_model_on_text(combined_content)

        time.sleep(3)
        current_usage = auth_client.get_token_usage()
        tokens_used = current_usage - usage_before

        if tokens_used <= 0:
            time.sleep(2)
            current_usage = auth_client.get_token_usage()
            tokens_used = current_usage - usage_before
        model = get_model_name()
        if not model:
            showInfo("Error: No model selected. Please select a model in settings.")
            return

        showInfo(f"Model Used: {model}")
        showInfo(
            f"Training completed!\n\nTokens used in this session: {tokens_used:,}\nTotal token usage: {current_usage:,}"
        )

    except Exception as e:
        import traceback
        showInfo(f"Error in train_from_deck: {str(e)}\n\n{traceback.format_exc()}")
        try:
            error_log = os.path.join(addon_dir, "error_log.txt")
            with open(error_log, "a", encoding="utf-8") as f:
                f.write(f"{datetime.now()} - Error in train_from_deck:\n")
                f.write(f"{str(e)}\n")
                f.write(f"{traceback.format_exc()}\n\n")
        except Exception:
            pass




def extract_deck_content(deck_name=None):
    col = mw.col
    if not col:
        return ""
    if deck_name:
        did = col.decks.id(deck_name)
        card_ids = col.find_cards(f"did:{did}")
    else:
        card_ids = col.find_cards("deck:*")
    content = []
    for card_id in card_ids:
        card = col.get_card(card_id)
        note = card.note()
        for field in note.keys():
            field_content = note[field]
            if field_content:
                field_content = re.sub(r'<[^>]+>', '', field_content)
                if field_content.strip():
                    content.append(field_content.strip())
    return "\n\n".join(content)


# Add hooks
gui_hooks.deck_browser_did_render.append(inject_train_buttons)

# Uncomment the webview message handler
#showInfo("Registering webview message handler", parent=mw)
gui_hooks.webview_did_receive_js_message.append(handle_webview_message)

import os

def get_icon_path(icon_name):
    # Get the absolute path to the icons directory
    addon_dir = os.path.dirname(os.path.abspath(__file__))
    icon_dir = os.path.join(addon_dir, "icons")
    icon_path = os.path.join(icon_dir, icon_name)
    return icon_path