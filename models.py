from PyQt6.QtCore import QThread, pyqtSignal
import os
import requests
import re
import json
from aqt.utils import showInfo
from .shared import require_access_key, user_access_key, questions_cycle, get_model_name

# Global variables
uploaded_txt_content = {"content": ""}


#@require_access_key
#This decorator here causes crashes when the worker is run from the GUI... DO NOT USE IT HERE
class QuestionWorker(QThread):
    finished = pyqtSignal(str, list)
    error = pyqtSignal(str)

    def __init__(self, user_answer=None, question=None):
        super().__init__()
        self.user_answer = user_answer
        self.question = question


    def run(self):
        try:
            if self.user_answer is not None and self.question is not None:
                # Answer checking via server
                from .main import together_api_input
                output, total_tokens = together_api_input(self.user_answer, self.question)
                self.finished.emit(output, total_tokens)
            else:
                # Question generation via server
                from . import auth_client as global_auth_client
                from .ClientAuth import AuthClient
                client = global_auth_client if global_auth_client and global_auth_client.is_authenticated() else AuthClient()
                if not client.is_authenticated():
                    raise Exception("Not authenticated. Please log in first.")

                questions, total_tokens = client.generate_questions(uploaded_txt_content.get('content', '').strip(), model_hint=get_model_name())
                # Update local cache for later deck insertion
                questions_cycle["questions"] = questions
                questions_cycle["index"] = 0
                # Emit both raw text and list
                self.finished.emit("\n".join(questions), questions)
        except Exception as e:
            self.error.emit(str(e))