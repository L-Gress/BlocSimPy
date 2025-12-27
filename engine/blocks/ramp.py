from ..models import BlockModel

class Ramp(BlockModel):
    """Generates a signal that starts at a specific value and changes at a constant rate."""
    
    BLOCK_INFO = {
        "description": "Generates a linearly increasing or decreasing signal",
        "parameters": "Slope, Start Time, Initial Output",
        "formula": "Output = Initial + Slope * (t - StartTime) if t > StartTime else Initial",
        "usage": "Generate test ramps, time-varying setpoints, or linear sweeps",
        "category": "Sources"
    }
    
    def __init__(self):
        super().__init__("Ramp")
        self.add_output("out")
        self.add_param("Slope", 1.0)
        self.add_param("Start Time", 0.0)
        self.add_param("Initial Output", 0.0)
        self._cache_params()

    def _cache_params(self):
        try:
            self._slope = float(self.params.get("Slope", 1.0))
            self._start_t = float(self.params.get("Start Time", 0.0))
            self._init_out = float(self.params.get("Initial Output", 0.0))
        except:
            self._slope = 1.0
            self._start_t = 0.0
            self._init_out = 0.0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        if t <= self._start_t:
            self.outputs["out"].value = self._init_out
        else:
            self.outputs["out"].value = self._init_out + self._slope * (t - self._start_t)

    def compute_chunk(self, t_vec, dt, context=None):
        # Vectorized Ramp generation
        # We can use np.where or standard arithmetic since it's element-wise
        # cond = t_vec > self._start_t
        # res = self._init_out + self._slope * (t_vec - self._start_t)
        # out = np.where(cond, res, self._init_out)
        
        # Or faster: max(0, t - start) * slope + init 
        # But we need exactly init if t <= start.
        # (t - start) is negative.
        # So we want slope * max(0, t - start) + init ?
        # If t < start, slope*(negative) would be subtracted if we didn't clamp.
        # If we want output = init, then yes, slope*0 + init = init.
        
        delta = t_vec - self._start_t
        delta = np.maximum(0.0, delta)
        self.outputs["out"].vector_value = self._init_out + self._slope * delta

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Ramp")
        layout = QFormLayout(dialog)
        le_slope = QLineEdit(str(self.params.get("Slope", 1.0)))
        le_start = QLineEdit(str(self.params.get("Start Time", 0.0)))
        le_init = QLineEdit(str(self.params.get("Initial Output", 0.0)))
        layout.addRow("Slope:", le_slope)
        layout.addRow("Start Time:", le_start)
        layout.addRow("Initial Output:", le_init)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        def save():
            try:
                self.params["Slope"] = float(le_slope.text())
                self.params["Start Time"] = float(le_start.text())
                self.params["Initial Output"] = float(le_init.text())
                self._cache_params()
            except: pass
        dialog.accepted.connect(save)
        return dialog
