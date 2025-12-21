from ..models import BlockModel
import numpy as np

class FFT(BlockModel):
    """
    FFT Block.
    Analyzes input signal and outputs the N most significant frequency components.
    """
    
    BLOCK_INFO = {
        "description": "Extracts the top N dominant frequency peaks from the signal",
        "parameters": "Num Peaks, Window Size",
        "formula": "Peak Analysis (Magnitude)",
        "usage": "Use to analyze signal frequency content. Sample rate is automatically inherited from the simulation context.",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("FFT")
        self.add_input("in")
        
        # Default parameters
        self.add_param("Num Peaks", 1)
        self.add_param("Window Size", 1024)
        
        self._buffer = None
        self._window = None
        self._buffer_idx = 0
        
        # Caching parameters for performance
        self._cached_window_size = 1024
        self._cached_num_peaks = 1
        
        self.needs_port_refresh = False
        self._setup_outputs()
        self._init_buffers()

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        # If params are updated (e.g. during deserialization), sync ports and buffers
        # We check hasattr(self, "_buffer") to ensure the block is fully initialized
        if name == "params" and hasattr(self, "_buffer"):
            if hasattr(self, "_setup_outputs"): self._setup_outputs()
            if hasattr(self, "_init_buffers"): self._init_buffers()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._setup_outputs()
        self._init_buffers()

    def _init_buffers(self):
        """Pre-allocate buffers based on window size."""
        try:
            self._cached_window_size = int(float(self.params.get("Window Size", 1024)))
            self._cached_num_peaks = int(float(self.params.get("Num Peaks", 1)))
        except:
            self._cached_window_size = 1024
            self._cached_num_peaks = 1
            
        if self._buffer is None or len(self._buffer) != self._cached_window_size:
            self._buffer = np.zeros(self._cached_window_size, dtype=np.float32)
            self._window = np.hanning(self._cached_window_size).astype(np.float32)
        self._buffer_idx = 0

    def _setup_outputs(self):
        """Dynamic output creation based on Num Peaks."""
        try:
            n = int(float(self.params.get("Num Peaks", 1)))
        except:
            n = 1
        
        current_outs = list(self.outputs.keys())
        target_outs = []
        for i in range(1, n + 1):
            target_outs.append(f"f{i}")
            target_outs.append(f"a{i}")
            
        if set(current_outs) != set(target_outs):
            self.outputs.clear()
            for out_name in target_outs:
                self.add_output(out_name)

    def reset(self):
        self._setup_outputs()
        self._init_buffers()

    def compute(self, t, dt, context=None):
        val = self.inputs["in"].value if "in" in self.inputs else 0.0
        
        # Use cached values to avoid expensive dictionary lookups
        window_size = self._cached_window_size
        num_peaks = self._cached_num_peaks
        
        self._buffer[self._buffer_idx] = val
        self._buffer_idx += 1
        
        # Only process when buffer is full
        if self._buffer_idx >= window_size:
            # Perform Real FFT
            # Apply precomputed window
            windowed_data = self._buffer * self._window
            fft_res = np.fft.rfft(windowed_data)
            
            # Get magnitudes
            magnitudes = np.abs(fft_res)
            # Normalize magnitudes
            # For Hann window, the scaling factor is ~4.0/N to recover peak amplitude
            # of a single sinusoid (2.0/N for the FFT symmetry * 2.0 for Hann loss).
            magnitudes = magnitudes * (4.0 / window_size)
            
            # Find peaks (using argpartition for speed if num_peaks is much smaller than N)
            if num_peaks < (len(magnitudes) // 10):
                indices = np.argpartition(magnitudes, -num_peaks)[-num_peaks:]
                indices = indices[np.argsort(magnitudes[indices])][::-1]
            else:
                indices = np.argsort(magnitudes)[-num_peaks:][::-1]
            
            # Inherit sample rate from dt
            sample_rate = 1.0 / dt if dt > 0 else 44100.0
            freq_step = sample_rate / window_size
            
            # Update outputs
            for i in range(num_peaks):
                idx = indices[i]
                freq = idx * freq_step
                amp = float(magnitudes[idx])
                
                if f"f{i+1}" in self.outputs:
                    self.outputs[f"f{i+1}"].value = freq
                if f"a{i+1}" in self.outputs:
                    self.outputs[f"a{i+1}"].value = amp
            
            # Reset buffer pointer
            self._buffer_idx = 0

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QLabel
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("FFT Settings")
        layout = QFormLayout(dialog)
        
        le_peaks = QLineEdit(str(self.params.get("Num Peaks", 1)))
        le_window = QLineEdit(str(self.params.get("Window Size", 1024)))
        
        layout.addRow("Number of Peaks:", le_peaks)
        layout.addRow("Window Size (samples):", le_window)
        layout.addRow("Sample Rate:", QLabel("<i>Automatic (Inherited)</i>"))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        original_accept = dialog.accept
        
        def save_and_accept():
            old_n = self.params.get("Num Peaks", 1)
            try:
                new_n = int(le_peaks.text())
                self.params["Num Peaks"] = new_n
                self.params["Window Size"] = int(le_window.text())
                
                if new_n != old_n:
                    self._setup_outputs()
                    self.needs_port_refresh = True
            except:
                pass
            original_accept()

        dialog.accept = save_and_accept
        
        # Note: We need a way to tell the UI that ports have changed.
        # This will be handled in the main window / items level if we return a flag.
        return dialog
