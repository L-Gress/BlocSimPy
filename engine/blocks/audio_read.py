from ..models import BlockModel
import wave
import struct
import numpy as np
import os

class AudioRead(BlockModel):
    """
    Audio Read Block.
    Reads a WAV file and outputs the signal.
    """
    
    BLOCK_INFO = {
        "description": "Reads audio from a .wav file and outputs the signal",
        "parameters": "Filename, Loop (Yes/No)",
        "formula": "Output = Signal[t * SampleRate]",
        "usage": "Inject pre-recorded audio or test signals into the graph.",
        "category": "IO"
    }
    
    def __init__(self):
        super().__init__("AudioRead")
        self.add_output("out")
        self.add_param("Filename", "")
        self.add_param("Loop", "Yes") # Yes/No
        
        self.samples = None
        self.file_sample_rate = 44100
        self.duration = 0.0

    def reset(self):
        """Load the audio file into memory."""
        filename = self.params.get("Filename", "")
        if not filename or not os.path.exists(filename):
            self.samples = None
            return

        try:
            with wave.open(filename, 'rb') as wf:
                self.file_sample_rate = wf.getframerate()
                n_frames = wf.getnframes()
                n_channels = wf.getnchannels()
                width = wf.getsampwidth()
                
                # Read all frames
                data = wf.readframes(n_frames)
                
                # Convert to numpy array
                if width == 1: # 8-bit unsigned
                    fmt = 'B'
                    mul = 1/128.0
                    off = -1.0
                elif width == 2: # 16-bit signed
                    fmt = 'h'
                    mul = 1/32768.0
                    off = 0.0
                else:
                    print(f"AudioRead: Unsupported sample width {width}")
                    self.samples = None
                    return
                
                # Unpack
                count = n_frames * n_channels
                samples = np.frombuffer(data, dtype='B' if width==1 else '<i2')
                
                # Convert to float and normalize to [-1, 1]
                if width == 1:
                    samples = (samples.astype(np.float32) - 128) / 128.0
                else:
                    samples = samples.astype(np.float32) / 32768.0
                
                # If multi-channel, just take the first channel or average?
                # Let's take the first channel for simplicity in a mono sim
                if n_channels > 1:
                    self.samples = samples[::n_channels]
                else:
                    self.samples = samples
                
                self.duration = len(self.samples) / self.file_sample_rate
                
        except Exception as e:
            print(f"AudioRead Error loading {filename}: {e}")
            self.samples = None

    def compute(self, t, dt):
        if self.samples is None or len(self.samples) == 0:
            self.outputs["out"].value = 0.0
            return

        loop = self.params.get("Loop", "Yes") == "Yes"
        
        if not loop and t > self.duration:
            self.outputs["out"].value = 0.0
            return
            
        # Linear interpolation for better quality if sim rate != file rate
        exact_idx = t * self.file_sample_rate
        
        if loop:
            exact_idx = exact_idx % len(self.samples)
        
        idx_floor = int(np.floor(exact_idx))
        idx_ceil = idx_floor + 1
        frac = exact_idx - idx_floor
        
        # Boundary checks
        if idx_ceil >= len(self.samples):
            if loop:
                idx_ceil = 0
            else:
                idx_ceil = len(self.samples) - 1
        
        if idx_floor >= len(self.samples):
            if loop:
                idx_floor = 0
            else:
                idx_floor = len(self.samples) - 1

        val = (1.0 - frac) * self.samples[idx_floor] + frac * self.samples[idx_ceil]
        self.outputs["out"].value = float(val)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog, QPushButton, QHBoxLayout, QComboBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Audio Read Settings")
        layout = QFormLayout(dialog)
        
        # Filename
        file_layout = QHBoxLayout()
        le_file = QLineEdit(self.params.get("Filename", ""))
        btn_browse = QPushButton("...")
        file_layout.addWidget(le_file)
        file_layout.addWidget(btn_browse)
        
        def browse():
            f, _ = QFileDialog.getOpenFileName(dialog, "Open Audio", le_file.text(), "WAV Files (*.wav)")
            if f:
                le_file.setText(f)
                
        btn_browse.clicked.connect(browse)
        layout.addRow("WAV File:", file_layout)
        
        # Loop
        cb_loop = QComboBox()
        cb_loop.addItems(["Yes", "No"])
        cb_loop.setCurrentText(self.params.get("Loop", "Yes"))
        layout.addRow("Loop:", cb_loop)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        original_accept = dialog.accept
        
        def save_and_accept():
            self.params["Filename"] = le_file.text()
            self.params["Loop"] = cb_loop.currentText()
            original_accept()

        dialog.accept = save_and_accept
        
        return dialog
