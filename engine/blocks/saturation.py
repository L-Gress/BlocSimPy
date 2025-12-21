from ..models import BlockModel
import numpy as np

class Saturation(BlockModel):
    """Clamps the input signal between upper and lower limits."""
    
    BLOCK_INFO = {
        "description": "Clamps the input signal between upper and lower limits",
        "parameters": "Upper Limit, Lower Limit",
        "formula": "Output = min(Upper, max(Lower, Input))",
        "usage": "Prevent signal clipping, implement hard limiting, or model physical constraints",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Saturation")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Upper Limit", 1.0)
        self.add_param("Lower Limit", -1.0)
        self._cache_params()

    def _cache_params(self):
        try:
            self._upper = float(self.params.get("Upper Limit", 1.0))
            self._lower = float(self.params.get("Lower Limit", -1.0))
        except:
            self._upper = 1.0
            self._lower = -1.0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        val = self.inputs["in"].value
        res = max(self._lower, min(self._upper, val))
        self.outputs["out"].value = float(res)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Saturation")
        layout = QFormLayout(dialog)
        le_up = QLineEdit(str(self.params.get("Upper Limit", 1.0)))
        le_lo = QLineEdit(str(self.params.get("Lower Limit", -1.0)))
        layout.addRow("Upper Limit:", le_up)
        layout.addRow("Lower Limit:", le_lo)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        def save():
            try:
                self.params["Upper Limit"] = float(le_up.text())
                self.params["Lower Limit"] = float(le_lo.text())
                self._cache_params()
            except: pass
        dialog.accepted.connect(save)
        return dialog
