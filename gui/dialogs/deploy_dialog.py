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
        
        # Execution Mode
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Auto Detect", "Audio Driven", "Timer Driven"])
        self.mode_combo.currentTextChanged.connect(self._update_fields)
        form_layout.addRow("Execution Mode:", self.mode_combo)
        
        # Settings Stack (Simplified as shared fields for now)
        # We'll share fields but change labels/visibility logic if needed contextually
        # For now, let's keep it simple: Rate/Step Size and Block/Buffer Size
        
        self.rate_label = QLabel("Sample Rate (Hz):")
        self.rate_spin = QSpinBox()
        self.rate_spin.setRange(1, 100000)
        self.rate_spin.setValue(44100)
        form_layout.addRow(self.rate_label, self.rate_spin)
        
        self.size_label = QLabel("Buffer Size (samples):")
        self.size_spin = QSpinBox()
        self.size_spin.setRange(1, 8192)
        self.size_spin.setValue(1024)
        form_layout.addRow(self.size_label, self.size_spin)
        
        layout.addLayout(form_layout)
        
        layout.addWidget(QLabel("<i>ensure server is running</i>"))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
        self._update_fields(self.mode_combo.currentText())

    def _update_fields(self, mode):
        if mode == "Timer Driven":
            self.rate_label.setText("Frequency (Hz):")
            self.size_label.setText("Steps per Batch:")
            if self.rate_spin.value() == 44100: self.rate_spin.setValue(100) # Default to 100Hz for control
            if self.size_spin.value() == 1024: self.size_spin.setValue(1)
        else:
            self.rate_label.setText("Sample Rate (Hz):")
            self.size_label.setText("Buffer Size:")
            if self.rate_spin.value() == 100: self.rate_spin.setValue(44100)
        
    def get_settings(self):
        return {
            "url": self.url_edit.text(),
            "execution_mode": self.mode_combo.currentText(),
            "sample_rate": self.rate_spin.value(),
            "buffer_size": self.size_spin.value()
        }
