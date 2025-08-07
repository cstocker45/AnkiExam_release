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
                # This is for answer checking, not question generation
                from .main import together_api_input
                output, total_tokens = together_api_input(self.user_answer, self.question)
                self.finished.emit(output, total_tokens)
            else:
                # This is for question generation
                api_key = "642e67dafec91ef10ce54cf830e7af8d8112a17587b4941c470f8f5e34671514"
                if not api_key:
                    raise Exception("TOGETHER_API_KEY environment variable not set.")

                url = "https://api.together.xyz/v1/chat/completions"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                }
                data = {
                    "model": get_model_name(),  # Using the imported get_model_name function
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "Your task is to create 10 expert-level questions that test the user's understanding of the material. "
                                "Do NOT repeat or include the training data in your response. Only output the questions as a numbered list.\n\n"
                                "Training Data:\n"
                                f"{uploaded_txt_content.get('content', '').strip()}\n\n"
                                "Important: Each question should be properly formatted with correct spelling and punctuation. "
                                "Do not include any extra spaces or formatting characters."
                            )
                        },
                        {
                            "role": "user",
                            "content": "Generate a list of questions based on the provided training data. Only output the questions."
                        }
                    ]
                }

                response = requests.post(url, headers=headers, json=data)
                response.raise_for_status()
                result = response.json()
                questions_text = result["choices"][0]["message"]["content"]
                
                # Calculate and track token usage
                total_tokens = result.get("usage", {}).get("total_tokens", 0)
                print(f"API returned total_tokens: {total_tokens}")  # Debug logging
                
                if total_tokens > 0:
                    # Use the auth_client from the parent module
                    from . import auth_client
                    if auth_client and auth_client.is_authenticated():
                        success = auth_client.add_tokens(total_tokens)
                        print(f"Token update success: {success}")  # Debug logging
                    else:
                        print("Warning: auth_client not available or not authenticated")

                questions = re.findall(r"\d+\.\s.*?(?=(?:\n\d+\.|\Z))", questions_text, re.DOTALL)
                questions = [q.strip().replace("  ", " ") for q in questions]

                # Pass both questions and token count
                self.finished.emit(questions_text, questions)
        except Exception as e:
            self.error.emit(str(e))