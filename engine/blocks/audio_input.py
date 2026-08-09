import sounddevice as sd
import numpy as np
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                               QDialogButtonBox, QPushButton, QMessageBox, QApplication)
from ..models import BlockModel

class AudioDeviceDialog(QDialog):
    def __init__(self, params, mode="input", parent=None):
        super().__init__(parent)
        self.params = params
        self.mode = mode
        self.setWindowTitle(f"Audio {mode.capitalize()} Configuration")
        self.resize(400, 180)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # Channel Selector
        self.combo_channel = QComboBox()
        for i in range(16): 
            self.combo_channel.addItem(f"Channel {i}", i)
        current_ch = self.params.get("Channel", 0)
        self.combo_channel.setCurrentIndex(current_ch if isinstance(current_ch, int) else 0)
        form.addRow("Channel:", self.combo_channel)
        
        # Device Selector
        self.combo_device = QComboBox()
        self.combo_device.addItem("Default System Device", "default")
        
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            for i, dev in enumerate(devices):
                if mode == "input" and dev['max_input_channels'] > 0:
                    api_name = hostapis[dev['hostapi']]['name']
                    self.combo_device.addItem(f"[{i}] {dev['name']} ({api_name})", i)
                elif mode == "output" and dev['max_output_channels'] > 0:
                    api_name = hostapis[dev['hostapi']]['name']
                    self.combo_device.addItem(f"[{i}] {dev['name']} ({api_name})", i)
        except:
            pass

        current_dev = self.params.get("Device", "default")
        if current_dev != "default":
            idx = self.combo_device.findData(current_dev)
            if idx >= 0: self.combo_device.setCurrentIndex(idx)

        form.addRow("Device:", self.combo_device)
        
        # Test Button
        self.btn_test = QPushButton(f"Test {mode.capitalize()}")
        self.btn_test.clicked.connect(self.test_device)
        form.addRow("", self.btn_test)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def test_device(self):
        dev = self.combo_device.currentData()
        dev = None if dev == "default" else dev
        try:
            fs = 44100
            if self.mode == "input":
                self.btn_test.setText("Recording...")
                QApplication.processEvents()
                # Record 1s
                rec = sd.rec(int(fs), samplerate=fs, channels=1, device=dev, blocking=True, latency='low')
                amp = np.max(np.abs(rec))
                QMessageBox.information(self, "Result", f"Max Amplitude: {amp:.4f}\n(If 0.0, check OS permissions)")
            else:
                self.btn_test.setText("Playing...")
                QApplication.processEvents()
                t = np.linspace(0, 1, fs, False)
                # Play 1s sine
                sd.play(0.5 * np.sin(2*np.pi*440*t), fs, device=dev, blocking=True, latency='low')
            self.btn_test.setText(f"Test {self.mode.capitalize()}")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            self.btn_test.setText(f"Test {self.mode.capitalize()}")

    def accept(self):
        self.params["Channel"] = self.combo_channel.currentData()
        self.params["Device"] = self.combo_device.currentData()
        super().accept()

class AudioInput(BlockModel):
    BLOCK_INFO = {
        "description": "Captures realtime audio input",
        "parameters": "Channel, Device",
        "formula": "Output = AudioStream[Channel]",
        "usage": "Double-click to configure.",
        "category": "IO"
    }
    
    def __init__(self):
        super().__init__("AudioInput")
        self.add_output("out")
        self.add_param("Channel", 0)
        self.add_param("Device", "default")
        self._cached_channel = 0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params":
            try:
                self._cached_channel = int(float(self.params.get("Channel", 0)))
            except:
                self._cached_channel = 0

    def compute(self, t, dt, context=None):
        if context and context.indata is not None:
            ch = self._cached_channel
            if ch < context.indata.shape[1]:
                self.outputs["out"].value = float(context.indata[context.frame_idx, ch])

    def compute_chunk(self, t_vec, dt, context=None):
        if context and context.indata is not None:
            ch = self._cached_channel
            if ch < context.indata.shape[1]:
                # Directly assign the buffer slice to the output port
                self.outputs["out"].vector_value = context.indata[:, ch]

    def get_editor_dialog(self, parent=None):
        dialog = AudioDeviceDialog(self.params, mode="input", parent=parent)

        # AudioDeviceDialog.accept() mutates self.params in place, which
        # doesn't fire the __setattr__ hook that refreshes _cached_channel.
        original_accept = dialog.accept

        def accept_with_cache_refresh():
            original_accept()
            self.params = self.params

        dialog.accept = accept_with_cache_refresh
        return dialog