from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, QComboBox, 
                               QDialogButtonBox, QLabel, QPushButton, QMessageBox, QApplication)
import sounddevice as sd
import numpy as np
import time

class AudioDeviceDialog(QDialog):
    """
    Dialog for configuring Audio Input/Output blocks.
    Allows selecting a specific audio device from the system.
    """
    def __init__(self, params, mode="input", parent=None):
        super().__init__(parent)
        self.params = params
        self.mode = mode # "input" or "output"
        self.setWindowTitle("Audio Configuration")
        self.resize(400, 150)
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        # 1. Channel Selector
        self.combo_channel = QComboBox()
        for i in range(16): # 0-15
            self.combo_channel.addItem(str(i))
        current_ch = str(self.params.get("Channel", 0))
        self.combo_channel.setCurrentText(current_ch)
        form.addRow("Channel:", self.combo_channel)
        
        # 2. Device Selector
        self.combo_device = QComboBox()
        self.combo_device.addItem("Default System Device", "default")
        
        # Query Devices
        try:
            devices = sd.query_devices()
            hostapis = sd.query_hostapis()
            
            for i, dev in enumerate(devices):
                # Filter by capability
                if self.mode == "input" and dev['max_input_channels'] > 0:
                    api_name = hostapis[dev['hostapi']]['name']
                    name = f"[{i}] {dev['name']} ({api_name})"
                    self.combo_device.addItem(name, i) # Store index as data
                elif self.mode == "output" and dev['max_output_channels'] > 0:
                    api_name = hostapis[dev['hostapi']]['name']
                    name = f"[{i}] {dev['name']} ({api_name})"
                    self.combo_device.addItem(name, i)
                    
        except Exception as e:
            self.combo_device.addItem(f"Error querying devices: {e}", None)

        # Set Current Selection
        current_dev = self.params.get("Device", "default")
        
        # Logic to match current setting
        if current_dev == "default":
            self.combo_device.setCurrentIndex(0)
        else:
            # Try to match index
            found = False
            for idx in range(self.combo_device.count()):
                data = self.combo_device.itemData(idx)
                # stored data is int index or "default" string
                # current_dev could be int index or string name
                
                # If current_dev is int, match data
                if isinstance(current_dev, int) and data == current_dev:
                    self.combo_device.setCurrentIndex(idx)
                    found = True
                    break
                # If current_dev is string (name substring), we might not match exact index easily
                # but let's try strict matching if possible
            
            if not found:
                 # If we have a custom string or mismatch, just add it as a custom entry?
                 # Or warn? Let's just default to 0 if not found, or add it.
                 pass

        form.addRow("Device:", self.combo_device)
        
        # 3. Test Button
        self.btn_test = QPushButton("Test Device")
        self.btn_test.clicked.connect(self.test_device)
        form.addRow("", self.btn_test)

        layout.addLayout(form)
        
        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def test_device(self):
        """Test the selected device."""
        device_data = self.combo_device.currentData()
        device_idx = None
        if isinstance(device_data, int):
            device_idx = device_data
        # If 'default', leave as None
        
        try:
            if self.mode == "output":
                # Play a 440Hz Sine Wave for 1 second
                fs = 44100
                duration = 1.0
                t = np.linspace(0, duration, int(fs * duration), False)
                audio = 0.5 * np.sin(2 * np.pi * 440 * t)
                
                # Check channel count
                dev_info = sd.query_devices(device_idx, 'output')
                chans = dev_info['max_output_channels']
                
                # Reshape to stereo if needed/possible, or just 1 channel mapping
                # sounddevice map expects (frames, channels)
                # We replicate mono to all channels or just play mono?
                # sd.play handles 1D array as mono -> maps to all? or just ch 1?
                # Let's try simple play
                
                self.btn_test.setEnabled(False)
                self.btn_test.setText("Playing...")
                QApplication.processEvents()
                
                sd.play(audio, fs, device=device_idx, blocking=True)
                
                self.btn_test.setText("Test Device")
                self.btn_test.setEnabled(True)
                
            elif self.mode == "input":
                # Record 1 second and show amplitude
                fs = 44100
                duration = 1.0
                
                self.btn_test.setEnabled(False)
                self.btn_test.setText("Recording...")
                QApplication.processEvents()
                
                myrecording = sd.rec(int(duration * fs), samplerate=fs, channels=1, device=device_idx, blocking=True)
                
                max_amp = np.max(np.abs(myrecording))
                
                self.btn_test.setText("Test Device")
                self.btn_test.setEnabled(True)
                
                QMessageBox.information(self, "Input Test", f"Recorded 1s.\nMax Amplitude: {max_amp:.4f}\n(Visible signal > 0.01 usually)")
                
        except Exception as e:
            QMessageBox.critical(self, "Test Failed", f"Error: {e}")
            self.btn_test.setText("Test Device")
            self.btn_test.setEnabled(True)

    def accept(self):
        # Save Channel
        try:
            self.params["Channel"] = int(self.combo_channel.currentText())
        except:
            pass
            
        # Save Device
        data = self.combo_device.currentData()
        # data is int index or "default" string
        self.params["Device"] = data
        
        super().accept()
