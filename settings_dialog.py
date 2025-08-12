from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
from PyQt6.QtCore import Qt

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
        # Populate from server-allowed models; fallback to basic free list on error
        self.api_to_label = {}
        self.label_to_api = {}
        try:
            from .ClientAuth import AuthClient
            client = AuthClient()
            if client.is_authenticated():
                resp = client.get_allowed_models()  # {"models": [{"label":..., "api":...}, ...]}
                models = resp.get("models", [])
                for m in models:
                    label = m.get("label")
                    api = m.get("api")
                    if label and api:
                        self.model_combo.addItem(label)
                        self.api_to_label[api] = label
                        self.label_to_api[label] = api
        except Exception:
            pass
        if self.model_combo.count() == 0:
            # Fallback
            defaults = [
                ("DeepSeek R1 Distill Llama 70B Free", "deepseek-ai/DeepSeek-R1-Distill-Llama-70B-free"),
                ("Llama 3.3 70B Instruct Turbo Free", "meta-llama/Llama-3.3-70B-Instruct-Turbo-Free"),
            ]
            for label, api in defaults:
                self.model_combo.addItem(label)
                self.api_to_label[api] = label
                self.label_to_api[label] = api
        # Reflect saved selection
        try:
            from .shared import get_model_name
            current_api_model = get_model_name()
            current_label = self.api_to_label.get(current_api_model)
            if not current_label and self.model_combo.count() > 0:
                current_label = self.model_combo.itemText(0)
            if current_label:
                self.model_combo.setCurrentText(current_label)
        except Exception:
            if self.model_combo.count() > 0:
                self.model_combo.setCurrentIndex(0)
        
        # Save button
        save_button = QPushButton("Save")
        save_button.clicked.connect(self.save_settings)
        
        layout.addWidget(model_label)
        layout.addWidget(self.model_combo)
        layout.addWidget(save_button)
        
        self.setLayout(layout)
    
    def save_settings(self):
        selected_label = self.model_combo.currentText()
        from .shared import set_model_name
        # Persist user's hint; server enforces actual allowed model
        api_value = self.label_to_api.get(selected_label)
        if api_value:
            set_model_name(api_value)
        self.accept()
