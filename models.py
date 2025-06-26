from PyQt6.QtCore import QThread, pyqtSignal
import os
import requests
import re
import json
from aqt.utils import showInfo
from .shared import require_access_key, user_access_key, questions_cycle

# Global variables
uploaded_txt_content = {"content": ""}

class QuestionWorker(QThread):
    finished = pyqtSignal(str, list)
    error = pyqtSignal(str)
    
    @require_access_key
    def run(self):
        try:
            api_key = "642e67dafec91ef10ce54cf830e7af8d8112a17587b4941c470f8f5e34671514"
            if not api_key:
                raise Exception("TOGETHER_API_KEY environment variable not set.")

            url = "https://api.together.xyz/v1/chat/completions"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": "deepseek-ai/DeepSeek-V3",
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
            questions_text = response.json()["choices"][0]["message"]["content"]

            questions = re.findall(r"\d+\.\s.*?(?=(?:\n\d+\.|\Z))", questions_text, re.DOTALL)
            questions = [q.strip().replace("  ", " ") for q in questions]

            self.finished.emit(questions_text, questions)
        except Exception as e:
            self.error.emit(str(e)) 