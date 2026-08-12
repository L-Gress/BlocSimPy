from ..models import BlockModel
import numpy as np

class SineWave(BlockModel):
    """Generates a sinusoidal waveform signal."""
    
    BLOCK_INFO = {
        "description": "Generates a sinusoidal waveform signal",
        "parameters": "Amplitude, Frequency (Hz), Phase (rad), Use External Time",
        "formula": "Output = Amplitude * sin(2*pi * Frequency * t + Phase)",
        "usage": "Use for testing systems with periodic inputs or generating oscillating signals",
        "category": "Sources"
    }
    
    def __init__(self):
        super().__init__("SineWave")
        self.add_output("out")
        self.add_param("Amplitude", 1.0)
        self.add_param("Frequency", 1.0)
        self.add_param("Phase", 0.0)
        self.add_param("Use External Time", "False") # "True" or "False"
        
        # Initialize caches and structure
        self._init_caches()
        self.update_io()

    def update_io(self):
        use_ext = self.params.get("Use External Time", "False") == "True"
        changed = False
        if use_ext:
            if "time" not in self.inputs:
                self.add_input("time")
                changed = True
        else:
            if "time" in self.inputs:
                del self.inputs["time"]
                changed = True
        
        if changed:
            self.needs_port_refresh = True

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params":
            if hasattr(self, "update_io"):
                self.update_io()
            if hasattr(self, "_cached_amp"):
                self._init_caches()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self.update_io()
        self._init_caches()

    def _init_caches(self):
        try:
            self._cached_amp = float(self.params.get("Amplitude", 1.0))
            self._cached_freq = float(self.params.get("Frequency", 1.0))
            self._cached_phase = float(self.params.get("Phase", 0.0))
        except:
            self._cached_amp = 1.0
            self._cached_freq = 1.0
            self._cached_phase = 0.0
        self._two_pi = 2.0 * np.pi

    def compute(self, t, dt, context=None):
        amp = self._cached_amp
        freq = self._cached_freq
        phase = self._cached_phase
        
        # Determine time source
        time_val = t
        if self.params.get("Use External Time", "False") == "True" and "time" in self.inputs:
            time_val = self.inputs["time"].value

        self.outputs["out"].value = amp * np.sin(self._two_pi * freq * time_val + phase)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QCheckBox, QDialogButtonBox
        from gui.widgets.param_value_editor import ParamValueEditor

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Edit {self.name}")
        layout = QFormLayout(dialog)

        # Amplitude
        amp_edit = ParamValueEditor(self.params.get("Amplitude", 1.0))
        layout.addRow("Amplitude:", amp_edit)

        # Frequency
        freq_edit = ParamValueEditor(self.params.get("Frequency", 1.0))
        layout.addRow("Frequency (Hz):", freq_edit)

        # Phase
        phase_edit = ParamValueEditor(self.params.get("Phase", 0.0))
        layout.addRow("Phase (rad):", phase_edit)

        # External Time
        cb_ext_time = QCheckBox()
        is_checked = self.params.get("Use External Time", "False") == "True"
        cb_ext_time.setChecked(is_checked)
        layout.addRow("Use External Time:", cb_ext_time)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            self.params["Amplitude"] = amp_edit.get_value()
            self.params["Frequency"] = freq_edit.get_value()
            self.params["Phase"] = phase_edit.get_value()
            self.params["Use External Time"] = "True" if cb_ext_time.isChecked() else "False"

            self.update_io()
            self._init_caches()
            original_accept()

        dialog.accept = accept_with_save
        return dialog
