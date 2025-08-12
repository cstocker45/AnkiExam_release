from aqt import mw
from aqt.utils import showInfo
from aqt.qt import *
from anki.notes import Note
#from .__init__ import questions_cycle
from PyQt6.QtCore import QThread, pyqtSignal
from .shared import questions_cycle, require_access_key, user_access_key
from PyQt6.QtWidgets import QLabel
from PyQt6.QtGui import QMovie

from datetime import datetime

NOTE_TYPE_NAME = "AnkiExam Card"
QUESTION_FIELD = "Question"
ANSWER_FIELD = "Answer"



def ensure_note_type():
    col = mw.col
    mm = col.models
    model = mm.by_name(NOTE_TYPE_NAME)
    if not model:
        model = mm.new(NOTE_TYPE_NAME)
        mm.addField(model, mm.newField(QUESTION_FIELD))
        mm.addField(model, mm.newField(ANSWER_FIELD))
        tmpl = mm.newTemplate("Card 1")
        # Use type:Answer to get an input box with id="typeans"
        #for some reason the actual id is "ankiExamAnswer" in the HTML
        #tmpl['qfmt'] = f"{{{{{QUESTION_FIELD}}}}}<hr>{{{{type:Answer}}}}"
        tmpl['qfmt'] = f"""{{{{{QUESTION_FIELD}}}}}<hr><input type="text" id="ankiExamAnswer" autofocus>"""
        tmpl['afmt'] = f"{{{{FrontSide}}}}<hr id=answer>{{{{{ANSWER_FIELD}}}}}"
        mm.addTemplate(model, tmpl)
        model['css'] += """
#typeans,
#ankiExamAnswer {
    background: yellow !important;
    width: 90% !important;
    height: 3em !important;
    font-size: 2em !important;
    padding: 0.5em !important;
}
""" # Add custom CSS to style the answer input box
        mm.add(model)
        mm.save(model)
        return model
    return model



#For some reason the css isnt being set correctly when im creating the card and at some point its creating 'ankiExamAnswer' seperate from
#the usual typeans input... idk why... so technically we can get around this by injecting JS but this is potentially very error prone...
def style_anki_exam_answer_js():
    js = """
    (function() {
        var el = document.getElementById('ankiExamAnswer');
        if (el && el.tagName.toLowerCase() === 'input') {
            // Create a textarea to replace the input
            var ta = document.createElement('textarea');
            ta.id = el.id;
            ta.value = el.value;
            ta.autofocus = true;
            ta.style.width = "80%";
            ta.style.height = "5em";
            ta.style.fontSize = "1em";
            ta.style.padding = "0.5em";
            ta.style.whiteSpace = "pre-wrap";
            ta.style.wordWrap = "break-word";
            ta.style.overflowY = "auto";
            ta.style.margin = "0 auto";  // Center horizontally
            ta.style.display = "block";   // Enable flexbox
            ta.style.marginLeft = "auto";
            ta.style.marginRight = "auto";
            ta.style.textAlign = "center";
            ta.style.resize = "none";
            el.parentNode.replaceChild(ta, el);
        } else if (el && el.tagName.toLowerCase() === 'textarea') {
            // Style existing textarea
            el.style.width = "80%";
            el.style.height = "5em";
            el.style.fontSize = "1em";
            el.style.padding = "0.5em";
            el.style.whiteSpace = "pre-wrap";
            el.style.wordWrap = "break-word";
            el.style.overflowY = "auto";
            el.style.margin = "0 auto";  // Center horizontally
            el.style.display = "block";   // Enable flexbox
            el.style.flexDirection = "column";  // Stack content vertically
            el.style.alignItems = "center";     // Center content horizontally
            el.style.justifyContent = "center"; 
            el.style.marginLeft = "auto";
            el.style.marginRight = "auto";
            el.style.textAlign = "center";
            el.style.resize = "none";
        }
    })();
    """
    mw.reviewer.web.eval(js)

#commented out settings
#el.style.background = "#f3e8ff";
#ta.style.background = "#f3e8ff";
#ta.style.color = "black";
#el.style.color = "black";

from aqt import gui_hooks
gui_hooks.reviewer_did_show_question.append(lambda *a, **k: style_anki_exam_answer_js())


#keep answer on the backside
def retain_anki_exam_answer_js():
    js = """
    (function() {
        var el = document.getElementById('ankiExamAnswer');
        if (el) {
            // Restore previous value if present
            if (window._ankiExamAnswer !== undefined) {
                el.value = window._ankiExamAnswer;
            }
            // Save value on input
            el.addEventListener('input', function() {
                window._ankiExamAnswer = el.value;
            });
        }
    })();
    """
    mw.reviewer.web.eval(js)

#pull input from cache and also insert js for changing style again... this is a lot of js inserts... suboptimal.
gui_hooks.reviewer_did_show_question.append(lambda *a, **k: retain_anki_exam_answer_js())
gui_hooks.reviewer_did_show_answer.append(lambda *a, **k: style_anki_exam_answer_js())
gui_hooks.reviewer_did_show_answer.append(lambda *a, **k: retain_anki_exam_answer_js())


def add_questions_to_deck(deck_id=None):
    """Add generated questions to a new or existing deck."""
    if not mw.col:
        showInfo("Anki collection not available.")
        return
        
    # Create a new deck if no deck_id provided
    if deck_id is None:
        deck_name = f"AnkiExam Questions {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        deck_id = mw.col.decks.id(deck_name)
    
    # Get note type
    model = ensure_note_type()
    if not model:
        showInfo("Could not create note type.")
        return
        
    # Set the deck as current
    mw.col.decks.select(deck_id)
    
    # Set the deck ID in the model
    model['did'] = deck_id
    mw.col.models.save(model)
    
    # Add notes
    added_count = 0
    if not questions_cycle["questions"]:
        showInfo("No questions found in questions_cycle")
        return
    
    for q in questions_cycle["questions"]:
        try:
            # Create note
            note = Note(mw.col, model)
            note[QUESTION_FIELD] = q
            note[ANSWER_FIELD] = ""
            
            # Add to collection
            mw.col.addNote(note)
            added_count += 1
        except Exception as e:
            showInfo(f"Error adding note: {str(e)}")
            continue
    
    # Save changes
    mw.col.reset()
    mw.reset()
    
    if added_count > 0:
        showInfo(f"Successfully added {added_count} cards to your deck.")
    else:
        showInfo("No cards were added to the deck.")



#DEBUG
def save_current_card_html(filename="/tmp/anki_card_debug.html"):
    reviewer = mw.reviewer
    if not reviewer:
        showInfo("Reviewer not available.")
        return
    def save_html(html):
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html)
        showInfo(f"Card HTML saved to {filename}")
    reviewer.web.evalWithCallback("document.documentElement.outerHTML;", save_html)


def save_current_card_html_hook(*args, **kwargs):
    save_current_card_html()

from aqt import gui_hooks
#gui_hooks.reviewer_did_show_answer.append(save_current_card_html_hook)



# Worker for API call
class AnswerWorker(QThread):
    finished = pyqtSignal(str, int)
    error = pyqtSignal(str)
    
    @require_access_key
    def __init__(self, user_answer, question):
        super().__init__()
        self.user_answer = user_answer
        self.question = question
        
    @require_access_key
    def run(self):
        try:
            from .main import together_api_input
            output, total_tokens = together_api_input(self.user_answer, self.question)
            self.finished.emit(output, total_tokens)
        except Exception as e:
            self.error.emit(str(e))

#Function to add the API button to the reviewer
def add_api_button_to_reviewer(obj):
    from anki.cards import Card
    if isinstance(obj, Card):
        card = obj
        note = card.note()
        reviewer = mw.reviewer
    else:
        reviewer = obj
        card = reviewer.card
        note = card.note()

    if note.model()['name'] != NOTE_TYPE_NAME:
        # if hasattr(mw, "_anki_exam_btn"):
        #     mw._anki_exam_btn.hide()
        return

    # --- Begin QWidget button logic (commented out, keep for future use) ---
    # if not hasattr(mw, "_anki_exam_btn"):
    #     btn = QPushButton("Check with API", mw)
    #     btn.setFixedWidth(140)
    #     btn.setFixedHeight(32)
    #     btn.move(120, mw.height() - 120)
    #
    #     def on_click():
    #         # Debug: Show current note type and template
    #         showInfo(f"Note type: {note.model()['name']}\nCard template: {card.template()['name']}")
    #         
    #         # Debug: Show which side is being shown
    #         showInfo(f"Reviewer state: {reviewer.state}")
    #
    #         # Debug: Show current HTML of the card
    #         def show_html(html):
    #             with open("/tmp/anki_card_debug.html", "w", encoding="utf-8") as f:
    #                 f.write(html)
    #             showInfo("Card HTML written to /tmp/anki_card_debug.html")
    #
    #         reviewer.web.evalWithCallback("document.documentElement.outerHTML;", show_html)
    #
    #         # Try to get the typed answer from the reviewer webview
    #         js = """
    #             (function() {
    #                 var el = document.getElementById('ankiExamAnswer');
    #                 if (!el) return "NO INPUT";
    #                 return el.value;
    #             })();
    #         """
    #
    #         def after_eval(user_answer):
    #             showInfo(f"JS returned: '{user_answer}'")
    #             user_answer = user_answer or ""
    #             if user_answer == "NO INPUT":
    #                 showInfo("Input box with id 'ankiExamAnswer' not found in the card HTML.")
    #                 return
    #             if not user_answer.strip():
    #                 showInfo("Please type your answer in the answer field first.")
    #                 return
    #
    #             # Show loading dialog (parented to mw)
    #             loading_dialog = QDialog(mw)
    #             loading_dialog.setWindowTitle("Checking Answer...")
    #             loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)
    #             loading_layout = QVBoxLayout()
    #             loading_label = QLabel("Contacting API, please wait...")
    #             loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    #             loading_layout.addWidget(loading_label)
    #             progress = QProgressBar()
    #             progress.setRange(0, 0)
    #             loading_layout.addWidget(progress)
    #             loading_dialog.setLayout(loading_layout)
    #             loading_dialog.setMinimumWidth(400)
    #             loading_dialog.setMinimumHeight(120)
    #             loading_dialog.show()
    #             loading_dialog.raise_()
    #             loading_dialog.activateWindow()
    #
    #             # Keep a reference to the worker to prevent GC
    #             mw._anki_exam_worker = AnswerWorker(user_answer, note[QUESTION_FIELD])
    #
    #             def on_finished(output, total_tokens):
    #                 loading_dialog.close()
    #                 showInfo(f"API Output:\n{output}\n\nTotal Tokens: {total_tokens}")
    #                 mw._anki_exam_worker = None  # Allow GC
    #                 # Show the answer after user closes the popup
    #                 reviewer = mw.reviewer
    #                 if hasattr(reviewer, "_showAnswer"):
    #                     reviewer._showAnswer()
    #                 elif hasattr(reviewer, "show_answer"):
    #                     reviewer.show_answer()
    #
    #             def on_error(error_msg):
    #                 loading_dialog.close()
    #                 showInfo(f"API Error: {error_msg}")
    #                 mw._anki_exam_worker = None  # Allow GC
    #
    #             mw._anki_exam_worker.finished.connect(on_finished)
    #             mw._anki_exam_worker.error.connect(on_error)
    #             mw._anki_exam_worker.start()
    #
    #         reviewer.web.evalWithCallback(js, after_eval)
    #     btn.clicked.connect(on_click)
    #     mw._anki_exam_btn = btn
    # mw._anki_exam_btn.show()
    # --- End QWidget button logic ---

    # Hide the "Show Answer" button for this note type and replace it with "Check with API"
    QTimer.singleShot(150, replace_show_answer_button)

from aqt import gui_hooks
gui_hooks.reviewer_did_show_question.append(add_api_button_to_reviewer)
#gui_hooks.reviewer_did_show_question.append(add_api_button_to_reviewer)




#Logic to hide the "Show Answer" button in the bottom bar
def hide_show_answer_button(*args, **kwargs):
    reviewer = mw.reviewer
    if hasattr(reviewer, "bottom") and hasattr(reviewer.bottom, "web"):
        js = """
        (function() {
            var btn = document.getElementById('ansbut');
            if (btn) {
                btn.style.display = "none";
                btn.disabled = true;
            }
        })();
        """
        def save_html(html):
            with open("/tmp/anki_bottom_bar.html", "w", encoding="utf-8") as f:
                f.write(html)
            #showInfo("Bottom bar HTML saved to /tmp/anki_bottom_bar.html")
        reviewer.bottom.web.evalWithCallback("document.documentElement.outerHTML;", save_html)
        reviewer.bottom.web.eval(js)
        #showInfo("Debug: JS injected to hide 'Show Answer' button in bottom webview.")
    else:
        pass


#save the html of the bottom bar
from aqt import gui_hooks
#gui_hooks.reviewer_did_show_question.append(hide_show_answer_button)


def replace_show_answer_button():
    reviewer = mw.reviewer
    js = """
    (function() {
        var btn = document.getElementById('ansbut');
        if (btn) {
            // Replace the visible text node only
            for (var i = 0; i < btn.childNodes.length; i++) {
                var node = btn.childNodes[i];
                if (node.nodeType === Node.TEXT_NODE && node.nodeValue.includes("Show Answer")) {
                    node.nodeValue = node.nodeValue.replace("Show Answer", "Check with API");
                    break;
                }
            }
            // Optionally update the title
            btn.title = "Check your answer with the API";
            // Update the click handler to use the bridge command
            btn.onclick = function() {
                pycmd('anki_exam_check_api');
            };
        }
    })();
    """
    reviewer.bottom.web.eval(js)

def on_bridge_cmd(cmd):
    #showInfo(f"on_bridge_cmd: received cmd={cmd}")
    if cmd == "anki_exam_check_api":
        #showInfo("on_bridge_cmd: matched anki_exam_check_api")
        reviewer = mw.reviewer
        card = reviewer.card
        note = card.note()

        def show_html(html):
            with open("/tmp/anki_card_debug.html", "w", encoding="utf-8") as f:
                f.write(html)
            #showInfo("Card HTML written to /tmp/anki_card_debug.html")

        reviewer.web.evalWithCallback("document.documentElement.outerHTML;", show_html)

        js = """
            (function() {
                var el = document.getElementById('ankiExamAnswer');
                if (!el) return "NO INPUT";
                return el.value;
            })();
        """
        @require_access_key 
        def after_eval(user_answer):
            #showInfo(f"on_bridge_cmd: JS returned: '{user_answer}'")
            user_answer = user_answer or ""
            if user_answer == "NO INPUT":
                #showInfo("on_bridge_cmd: Input box with id 'ankiExamAnswer' not found in the card HTML.")
                return
            if not user_answer.strip():
                #showInfo("on_bridge_cmd: Please type your answer in the answer field first.")
                return

            #Star the worker immediately
            worker = AnswerWorker(user_answer, note[QUESTION_FIELD])
            
            # Check if worker was created (might be None if access key check failed)
            if not worker:
                return
                
            worker.start()

            def on_finished(output, total_tokens):
                loading_dialog.close()
                reviewer = mw.reviewer
                mw._anki_exam_worker = None
                
                # Show the answer first
                if hasattr(reviewer, "_showAnswer"):
                    reviewer._showAnswer()
                elif hasattr(reviewer, "show_answer"):
                    reviewer.show_answer()
                
                # Wait for the answer field to be generated before injecting content
                def inject_content():
                    js = f"""
                    (function() {{
                        var answerField = document.getElementById('answer');
                        if (answerField) {{
                            // Create a textarea to replace the answer field
                            var ta = document.createElement('textarea');
                            ta.id = answerField.id;
                            
                            // Function to convert markdown-style formatting to HTML
                            function formatText(text) {{
                                // Convert **bold** to <b>bold</b>
                                text = text.replace(/\*\*(.*?)\*\*/g, '<b>$1</b>');
                                // Convert *italic* to <i>italic</i>
                                text = text.replace(/\*(.*?)\*/g, '<i>$1</i>');
                                return text;
                            }}
                            
                            // Format the output text
                            var formattedOutput = formatText(`{output}`);
                            
                            // Create a div to hold the formatted text
                            var div = document.createElement('div');
                            div.innerHTML = formattedOutput;
                            div.style.width = "80%";
                            div.style.height = "300px";
                            div.style.fontSize = "1em";
                            div.style.padding = "0.5em";
                            div.style.background = "var(--window-bg)";
                            div.style.color = "var(--text-fg)";
                            div.style.borderRadius = "4px";
                            div.style.border = "1px solid var(--border)";
                            div.style.whiteSpace = "pre-wrap";
                            div.style.wordWrap = "break-word";
                            div.style.overflowY = "auto";
                            div.style.margin = "0 auto";  // Center horizontally
                            div.style.display = "flex";   // Enable flexbox
                            div.style.flexDirection = "column";  // Stack content vertically
                            div.style.alignItems = "center";     // Center content horizontally
                            div.style.justifyContent = "center"; // Center content vertically
                            
                            // Replace the answer field with our formatted div
                            answerField.parentNode.replaceChild(div, answerField);

                            // Function to adjust font size
                            function adjustFontSize() {{
                                var fontSize = 1.0;
                                var minFontSize = 0.5;
                                var maxFontSize = 2.0;
                                
                                while (div.scrollHeight > div.clientHeight && fontSize > minFontSize) {{
                                    fontSize -= 0.1;
                                    div.style.fontSize = fontSize + "em";
                                }}
                                
                                while (div.scrollHeight < div.clientHeight && fontSize < maxFontSize) {{
                                    fontSize += 0.1;
                                    div.style.fontSize = fontSize + "em";
                                }}
                                
                                // Final adjustment to ensure no scroll
                                if (div.scrollHeight > div.clientHeight) {{
                                    fontSize -= 0.1;
                                    div.style.fontSize = fontSize + "em";
                                }}
                            }}

                            // Initial adjustment
                            adjustFontSize();
                            
                            // Adjust on window resize
                            window.addEventListener('resize', adjustFontSize);
                        }}
                    }})();
                    """
                    reviewer.web.eval(js)
                
                # Add a small delay to ensure the answer field exists
                QTimer.singleShot(100, inject_content)

            def on_error(error_msg):
                loading_dialog.close()
                showInfo(f"API Error: {error_msg}")
                try:
                    # Re-enable Anki's built-in answer button if present
                    reviewer = mw.reviewer if hasattr(mw, 'reviewer') else None
                    if reviewer and reviewer.bottom.web:
                        reviewer.bottom.web.eval("var b=document.getElementById('ansbut'); if(b){b.disabled=false; b.style.display='';}")
                except Exception:
                    pass
                loading_dialog.worker = None

            #what to do when the worker is finished or errors
            worker.finished.connect(on_finished)
            worker.error.connect(on_error)
            


            loading_dialog = QDialog(mw)
            loading_dialog.setWindowTitle("Checking Answer...")
            loading_dialog.setWindowModality(Qt.WindowModality.WindowModal)
            loading_layout = QVBoxLayout()
            
            # Create text areas for question and answer
            question_label = QLabel()
            question_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            question_label.setStyleSheet("font-size: 16px; margin-bottom: 16px;")
            question_label.setWordWrap(True)  # Enable word wrapping
            loading_layout.addWidget(question_label)
            
            answer_label = QLabel()
            answer_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
            answer_label.setStyleSheet("font-size: 16px;")
            answer_label.setWordWrap(True)  # Enable word wrapping
            loading_layout.addWidget(answer_label)
            
            # Add progress bar (initially hidden)
            progress = QProgressBar()
            progress.setRange(0, 0)
            progress.hide()
            loading_layout.addWidget(progress)

            #instead of a progress bar, add a spinner
            spinner = QLabel()
            movie = QMovie("path/to/spinner.gif")
            spinner.setMovie(movie)
            movie.start()
            spinner.show()
            loading_layout.addWidget(spinner)
            
            loading_dialog.setLayout(loading_layout)
            loading_dialog.setMinimumWidth(600)
            loading_dialog.setMinimumHeight(200)
            loading_dialog.show()
            loading_dialog.raise_()
            loading_dialog.activateWindow()

            # Function to type out text with animation
            def type_text(label, text, delay=20):
                label.setText("")  # Clear existing text
                text = text.strip()  # Remove leading/trailing whitespace
                current_text = ""
                
                def add_char(char_index):
                    if char_index < len(text):
                        nonlocal current_text
                        current_text += text[char_index]
                        label.setText(current_text)
                        # Add a small delay after spaces to make them more visible
                        next_delay = delay * 2 if text[char_index] == " " else delay
                        QTimer.singleShot(next_delay, lambda: add_char(char_index + 1))
                
                add_char(0)
                return len(text) * delay

            # Start typing animations
            question_delay = type_text(question_label, f"Question: {note[QUESTION_FIELD].strip()}")
            QTimer.singleShot(question_delay + 500, lambda: type_text(answer_label, f"Your Answer: {user_answer}"))
            
            # Show progress bar after animations
            def show_progress():
                progress.show()
                loading_label = QLabel("Contacting API, please wait...")
                loading_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                loading_layout.addWidget(loading_label)
            
            QTimer.singleShot(question_delay + 500, show_progress)

        #showInfo("on_bridge_cmd: about to eval JS for user answer")
        reviewer.web.evalWithCallback(js, after_eval)
        return True, None  # Mark as handled
    showInfo("on_bridge_cmd: not handled")
    return False, None  # Not handled

from aqt import gui_hooks
gui_hooks.webview_did_receive_js_message.append(
    lambda webview, msg, context: on_bridge_cmd(msg) if msg == "anki_exam_check_api" else (False, None)
)

#Reset the answer field when a new question is shown so text isnt carried over from last question.
def reset_anki_exam_answer_js():
    js = """
    (function() {
        window._ankiExamAnswer = "";
        var el = document.getElementById('ankiExamAnswer');
        if (el) {
            el.value = "";
            el.focus(); //focus the input box after clearing it.
        }
    })();
    """
    mw.reviewer.web.eval(js)

from aqt import gui_hooks
gui_hooks.reviewer_did_show_question.append(lambda *a, **k: reset_anki_exam_answer_js())   

@require_access_key
def create_anki_card(question, answer, deck_name="Default"):
    """
    Create an Anki card, requiring a valid access key
    """
    # ... rest of the function implementation ...

@require_access_key
def process_answer(user_answer, correct_answer):
    """
    Process and grade an answer, requiring a valid access key
    """


