from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                               QLineEdit, QComboBox, QDialogButtonBox, QLabel,
                               QSpinBox)

class DeployDialog(QDialog):
    """Dialog to configure deployment settings."""
    
    def __init__(self, parent=None, default_url="http://localhost:8080"):
        super().__init__(parent)
        self.setWindowTitle("Deploy to Realtime Server")
        self.resize(400, 200)
        
        layout = QVBoxLayout(self)
        
        form_layout = QFormLayout()
        
        self.url_edit = QLineEdit(default_url)
        form_layout.addRow("Server URL:", self.url_edit)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("Optional (if server secured)")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        form_layout.addRow("API Key:", self.api_key_edit)
        
        layout.addLayout(form_layout)
        
        layout.addWidget(QLabel("<i>ensure server is running</i>"))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_settings(self):
        return {
            "url": self.url_edit.text(),
            "api_key": self.api_key_edit.text()
        }
