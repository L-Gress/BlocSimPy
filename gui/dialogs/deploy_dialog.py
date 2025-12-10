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
        
        self.rate_combo = QComboBox()
        self.rate_combo.addItems(["44100", "48000", "22050", "8000"])
        form_layout.addRow("Sample Rate:", self.rate_combo)
        
        self.buffer_spin = QSpinBox()
        self.buffer_spin.setRange(64, 8192)
        self.buffer_spin.setValue(1024)
        form_layout.addRow("Buffer Size:", self.buffer_spin)
        
        layout.addLayout(form_layout)
        
        layout.addWidget(QLabel("<i>ensure realtime_server.py is running</i>"))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def get_settings(self):
        return {
            "url": self.url_edit.text(),
            "sample_rate": int(self.rate_combo.currentText()),
            "buffer_size": self.buffer_spin.value()
        }
