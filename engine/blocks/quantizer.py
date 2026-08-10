from ..models import BlockModel

class Quantizer(BlockModel):
    """Rounds the input to the nearest multiple of Interval (a stairstep)."""

    BLOCK_INFO = {
        "description": "Quantizes the input signal to discrete steps",
        "parameters": "Interval (step size)",
        "formula": "out = round(in / Interval) * Interval",
        "usage": "Model ADC/DAC resolution, discretized sensors, or stairstep effects",
        "category": "Discontinuities"
    }

    def __init__(self):
        super().__init__("Quantizer")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Interval", 0.5)
        self._cache_params()

    def _cache_params(self):
        try:
            interval = float(self.params.get("Interval", 0.5))
            self._interval = interval if interval != 0 else 0.5
        except:
            self._interval = 0.5

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        val = float(self.inputs["in"].value)
        out = round(val / self._interval) * self._interval
        self.outputs["out"].value = out

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Quantizer")
        layout = QFormLayout(dialog)
        le_interval = QLineEdit(str(self.params.get("Interval", 0.5)))
        layout.addRow("Interval:", le_interval)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        def save():
            try:
                self.params["Interval"] = float(le_interval.text())
                self._cache_params()
            except: pass
        dialog.accepted.connect(save)
        return dialog
