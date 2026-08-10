from ..models import BlockModel

class DeadZone(BlockModel):
    """Outputs zero for inputs within [Lower Limit, Upper Limit]; outside
    that band, passes through the input minus the nearest edge."""

    BLOCK_INFO = {
        "description": "Outputs zero for inputs within a dead band, passes the rest through",
        "parameters": "Upper Limit, Lower Limit",
        "formula": "0 if Lower<=in<=Upper; in-Upper if in>Upper; in-Lower if in<Lower",
        "usage": "Ignore small signals/noise near zero (or any band), e.g. mechanical play, sensor noise floors",
        "category": "Discontinuities"
    }

    def __init__(self):
        super().__init__("Dead Zone")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Upper Limit", 0.5)
        self.add_param("Lower Limit", -0.5)
        self._cache_params()

    def _cache_params(self):
        try:
            self._upper = float(self.params.get("Upper Limit", 0.5))
            self._lower = float(self.params.get("Lower Limit", -0.5))
        except:
            self._upper = 0.5
            self._lower = -0.5

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        val = float(self.inputs["in"].value)
        if val > self._upper:
            out = val - self._upper
        elif val < self._lower:
            out = val - self._lower
        else:
            out = 0.0
        self.outputs["out"].value = out

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Dead Zone")
        layout = QFormLayout(dialog)
        le_up = QLineEdit(str(self.params.get("Upper Limit", 0.5)))
        le_lo = QLineEdit(str(self.params.get("Lower Limit", -0.5)))
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
