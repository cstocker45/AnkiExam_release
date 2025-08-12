from PyQt6.QtCore import QThread, pyqtSignal


class AnswerWorker(QThread):
    finished = pyqtSignal(str, int)
    error = pyqtSignal(str)

    def __init__(self, user_answer: str, question: str):
        super().__init__()
        self.user_answer = user_answer
        self.question = question

    def run(self) -> None:
        try:
            # Route via server through together_api_input
            from .main import together_api_input
            output, total_tokens = together_api_input(self.user_answer, self.question)
            self.finished.emit(output, total_tokens)
        except Exception as exc:
            self.error.emit(str(exc))

