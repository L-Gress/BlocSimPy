import sounddevice as sd
import numpy as np
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                               QDialogButtonBox, QPushButton, QMessageBox, QApplication)
from ..models import BlockModel

class AudioDeviceDialog(QDialog):
    """
    Dialog for configuring Audio Output.
    Allows selecting a specific audio device and channel from the system.
    """
    def __init__(self, params, mode="output", parent=None):
        super().__init__(parent)
        self.params = params
        self.mode = mode
        self.setWindowTitle(f"Audio {mode.capitalize()} Configuration")
        self.resize(400, 180)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # 1. Channel Selector
        self.combo_channel = QComboBox()
        for i in range(16): 
            self.combo_channel.addItem(f"Channel {i}", i)
        
        current_ch = self.params.get("Channel", 0)
        self.combo_channel.setCurrentIndex(current_ch if isinstance(current_ch, int) and 0 <= current_ch < 16 else 0)
        form.addRow("Channel:", self.combo_channel)
        
        # 2. Device Selector
        self.combo_device = QComboBox()
        self.combo_device.addItem("Default System Device", "default")
        
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            for i, dev in enumerate(devices):
                if dev['max_output_channels'] > 0:
                    api_name = hostapis[dev['hostapi']]['name']
                    name = f"[{i}] {dev['name']} ({api_name})"
                    self.combo_device.addItem(name, i)
        except Exception as e:
            self.combo_device.addItem(f"Error: {e}", None)

        # Set Current Device
        current_dev = self.params.get("Device", "default")
        if current_dev == "default":
            self.combo_device.setCurrentIndex(0)
        else:
            found = False
            for idx in range(self.combo_device.count()):
                if self.combo_device.itemData(idx) == current_dev:
                    self.combo_device.setCurrentIndex(idx)
                    found = True
                    break
            if not found: self.combo_device.setCurrentIndex(0)

        form.addRow("Device:", self.combo_device)
        
        # 3. Test Button
        self.btn_test = QPushButton("Test Output")
        self.btn_test.clicked.connect(self.test_device)
        form.addRow("", self.btn_test)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def test_device(self):
        device_idx = self.combo_device.currentData()
        if device_idx == "default": device_idx = None
        
        try:
            fs = 44100
            duration = 1.0
            t = np.linspace(0, duration, int(fs * duration), False)
            audio = 0.5 * np.sin(2 * np.pi * 440 * t)
            
            self.btn_test.setEnabled(False)
            self.btn_test.setText("Playing...")
            QApplication.processEvents()
            
            sd.play(audio, fs, device=device_idx, blocking=True, latency='low')
            
            self.btn_test.setText("Test Output")
            self.btn_test.setEnabled(True)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.btn_test.setText("Test Output")
            self.btn_test.setEnabled(True)

    def accept(self):
        self.params["Channel"] = self.combo_channel.currentData()
        self.params["Device"] = self.combo_device.currentData()
        super().accept()

class AudioOutput(BlockModel):
    BLOCK_INFO = {
        "description": "Sends signal to realtime audio output",
        "parameters": "Channel, Device",
        "formula": "AudioStream[Channel] = Input",
        "usage": "Double-click to configure.",
        "category": "IO"
    }
    
    def __init__(self):
        super().__init__("AudioOutput")
        self.add_input("in")
        self.add_param("Channel", 0)
        self.add_param("Device", "default")
        
    def compute(self, t, dt):
        pass

    def get_editor_dialog(self, parent=None):
        return AudioDeviceDialog(self.params, mode="output", parent=parent)