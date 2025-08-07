from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QStandardItemModel

class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AnkiExam Settings")
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout()
        
        # Model selection
        model_label = QLabel("Select AI Model:")
        self.model_combo = QComboBox()
        self.model_combo.addItems([
            "DeepSeek V3-0324",
            "DeepSeek R1 Distill Llama 70B Free",
            "Llama 3.3 70B Instruct Turbo Free",
            "Llama 3.1 405B Instruct Turbo"
        ])
        # Disable non-free models
        self.non_free_labels = {"DeepSeek V3-0324", "Llama 3.1 405B Instruct Turbo"}
        model_obj = self.model_combo.model()
        if isinstance(model_obj, QStandardItemModel):
            for i in range(self.model_combo.count()):
                text = self.model_combo.itemText(i)
                if text in self.non_free_labels:
                    item = model_obj.item(i)
                    if item:
                        item.setEnabled(False)
        # Reflect saved selection
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
            if current_label in self.non_free_labels:
                current_label = "DeepSeek R1 Distill Llama 70B Free"
            self.model_combo.setCurrentText(current_label)
        except Exception:
            pass
        
        # Save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        
        layout.addWidget(model_label)
        layout.addWidget(self.model_combo)
        layout.addWidget(save_button)
        
        self.setLayout(layout)
    
    def save_settings(self):
        selected_model = self.model_combo.currentText()
        label_to_api = {
            "DeepSeek V3-0324": "deepseek-ai/DeepSeek-V3",
            "DeepSeek R1 Distill Llama 70B Free": "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free",
            "Llama 3.3 70B Instruct Turbo Free": "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free",
            "Llama 3.1 405B Instruct Turbo": "meta-llama/Meta-Llama-3.1-405B-Instruct-Turbo",
        }
        from .shared import set_model_name
        # Guard against non-free selections (should be disabled, but just in case)
        if selected_model in self.non_free_labels:
            selected_model = "DeepSeek R1 Distill Llama 70B Free"
        set_model_name(label_to_api.get(selected_model, "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"))
        self.accept()
