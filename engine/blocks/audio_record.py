from ..models import BlockModel
import wave
import struct

class AudioRecord(BlockModel):
    """
    Audio Record Block.
    Records input signal to a WAV file.
    """
    
    BLOCK_INFO = {
        "description": "Records audio to a .wav file",
        "parameters": "Filename, Sample Rate",
        "formula": "Writes input to disk",
        "usage": "Connect audio signal to record. Writes when simulation stops.",
        "category": "IO"
    }
    
    def __init__(self):
        super().__init__("AudioRecord")
        self.add_input("in")
        self.add_param("Filename", "output.wav")
        self.add_param("Sample Rate", 44100)
        
        self.file = None
        self.buffer = []
        self.is_recording = False

    def reset(self):
        """Prepare for recording."""
        filename = self.params.get("Filename", "output.wav")
        try:
            rate = int(float(self.params.get("Sample Rate", 44100)))
        except:
            rate = 44100
            
        # Ensure .wav extension
        if not filename.lower().endswith(".wav"):
            filename += ".wav"
            
        try:
            self.file = wave.open(filename, 'wb')
            self.file.setnchannels(1)
            self.file.setsampwidth(2) # 16-bit
            self.file.setframerate(rate)
            self.buffer = []
            self.is_recording = True
        except Exception as e:
            print(f"AudioRecord Error: {e}")
            self.is_recording = False
            self.file = None

    def compute(self, t, dt, context=None):
        if not self.is_recording or self.file is None:
            return
            
        val = self.inputs["in"].value if "in" in self.inputs else 0.0
        
        # Clip to -1.0 to 1.0 and scale to 16-bit
        if val > 1.0: val = 1.0
        elif val < -1.0: val = -1.0
        
        sample = int(val * 32767)
        self.buffer.append(sample)
        
        # Flush every ~4096 samples to keep memory usage low but IO reasonable
        if len(self.buffer) >= 4096:
            self._flush()

    def _flush(self):
        if self.file and self.buffer:
            try:
                # Pack as little endian signed short
                # struct.pack is fast enough for blocks
                data = struct.pack('<' + 'h'*len(self.buffer), *self.buffer)
                self.file.writeframes(data)
                self.buffer = []
            except Exception as e:
                print(f"AudioRecord Write Error: {e}")

    def stop(self):
        """Called when simulation stops."""
        if self.is_recording:
            self._flush()
            if self.file:
                try:
                    self.file.close()
                except:
                    pass
                self.file = None
            self.is_recording = False

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QFileDialog, QPushButton, QHBoxLayout
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Audio Record Settings")
        layout = QFormLayout(dialog)
        
        # Filename
        file_layout = QHBoxLayout()
        le_file = QLineEdit(self.params.get("Filename", "output.wav"))
        btn_browse = QPushButton("...")
        file_layout.addWidget(le_file)
        file_layout.addWidget(btn_browse)
        
        def browse():
            f, _ = QFileDialog.getSaveFileName(dialog, "Save Audio", le_file.text(), "WAV Files (*.wav)")
            if f:
                le_file.setText(f)
                
        btn_browse.clicked.connect(browse)
        layout.addRow("Filename:", file_layout)
        
        # Sample Rate
        le_rate = QLineEdit(str(self.params.get("Sample Rate", 44100)))
        layout.addRow("Sample Rate:", le_rate)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        original_accept = dialog.accept
        
        def save_and_accept():
            self.params["Filename"] = le_file.text()
            try:
                self.params["Sample Rate"] = float(le_rate.text())
            except:
                pass
            original_accept()

        dialog.accept = save_and_accept
        
        return dialog
