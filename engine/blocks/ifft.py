from ..models import BlockModel
import numpy as np

class IFFT(BlockModel):
    """
    IFFT Block (Sinusoidal Resynthesizer).
    Synthesizes a time-domain signal from N frequency/amplitude pairs.
    """
    
    BLOCK_INFO = {
        "description": "Reconstructs a signal from N frequency and amplitude peaks",
        "parameters": "Num Elements",
        "formula": "Output = Sum(Ai * sin(2*pi*Fi*t))",
        "usage": "Use in conjunction with FFT block to perform frequency domain manipulation. Sample rate is automatically inherited from the simulation context.",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("IFFT")
        self.add_output("out")
        
        # Parameters
        self.add_param("Num Elements", 1)
        
        self.phases = np.array([], dtype=np.float64)
        self._cached_num_elements = 1
        self._f_ports = [] # Cached PortModel objects
        self._a_ports = [] # Cached PortModel objects
        self._freqs_buf = np.array([], dtype=np.float64)
        self._amps_buf = np.array([], dtype=np.float64)
        
        # Subsampling for performance: only read inputs every N samples
        self._subsample_idx = 0
        self._subsample_rate = 128 # ~3ms at 44.1kHz
        self._two_pi = 2.0 * np.pi
        
        self.needs_port_refresh = False
        self._setup_inputs()

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        # Handle parameter updates during deserialization
        # We check hasattr(self, "_f_ports") to ensure the block is fully initialized
        if name == "params" and hasattr(self, "_f_ports"):
            if hasattr(self, "_setup_inputs"):
                self._setup_inputs()

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Re-sync internal ports and state after restoration
        self._setup_inputs()

    def _setup_inputs(self):
        """Dynamic input creation based on Num Elements."""
        try:
            self._cached_num_elements = int(float(self.params.get("Num Elements", 1)))
        except:
            self._cached_num_elements = 1
            
        n = self._cached_num_elements
        current_ins = list(self.inputs.keys())
        target_ins = []
        for i in range(1, n + 1):
            target_ins.append(f"f{i}")
            target_ins.append(f"a{i}")
            
        if set(current_ins) != set(target_ins):
            self.inputs.clear()
            self._f_ports = []
            self._a_ports = []
            for i in range(1, n + 1):
                f_name = f"f{i}"
                a_name = f"a{i}"
                self.add_input(f_name)
                self.add_input(a_name)
                self._f_ports.append(self.inputs[f_name])
                self._a_ports.append(self.inputs[a_name])
            
            # Reset buffers
            self.phases = np.zeros(n, dtype=np.float64)
            self._freqs_buf = np.zeros(n, dtype=np.float64)
            self._amps_buf = np.zeros(n, dtype=np.float64)

    def reset(self):
        self._setup_inputs()
        n = self._cached_num_elements
        self.phases = np.zeros(n, dtype=np.float64)
        self._freqs_buf = np.zeros(n, dtype=np.float64)
        self._amps_buf = np.zeros(n, dtype=np.float64)
        self._subsample_idx = 0

    def compute(self, t, dt, context=None):
        num_elements = self._cached_num_elements
        
        if len(self.phases) != num_elements:
            self._setup_inputs()
            
        # Subsampled input reading
        if self._subsample_idx == 0:
            for i in range(num_elements):
                self._freqs_buf[i] = self._f_ports[i].value
                self._amps_buf[i] = self._a_ports[i].value
        
        self._subsample_idx = (self._subsample_idx + 1) % self._subsample_rate
        
        # Phase and synthesis (must happen every sample)
        two_pi = self._two_pi
        
        # Accumulate phase to avoid discontinuities
        self.phases += two_pi * self._freqs_buf * dt
        # Keep phase in [0, 2pi]
        self.phases %= two_pi
        
        # Fast sum of sines
        # Using np.dot for weighted sum of sines is even faster than np.sum(a * b)
        total_val = np.dot(self._amps_buf, np.sin(self.phases))
        self.outputs["out"].value = float(total_val)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QLabel
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("IFFT Settings")
        layout = QFormLayout(dialog)
        
        le_elements = QLineEdit(str(self.params.get("Num Elements", 1)))
        layout.addRow("Number of Elements:", le_elements)
        layout.addRow("Sample Rate:", QLabel("<i>Automatic (Inherited)</i>"))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        original_accept = dialog.accept
        
        def save_and_accept():
            old_n = self.params.get("Num Elements", 1)
            try:
                new_n = int(le_elements.text())
                self.params["Num Elements"] = new_n
                
                if new_n != old_n:
                    self._setup_inputs()
                    self.needs_port_refresh = True
            except:
                pass
            original_accept()

        dialog.accept = save_and_accept
        return dialog
