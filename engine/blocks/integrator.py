from ..models import BlockModel
import numpy as np


class Integrator(BlockModel):
    """Integrator block - integrates signal over time."""
    
    BLOCK_INFO = {
        "description": "Integrates input signal over time using Euler method",
        "parameters": "Initial Condition",
        "formula": "Output(t) = IC + ∫Input(τ)dτ from 0 to t",
        "usage": "Accumulate values, model dynamic systems, or implement controllers"
    }
    
    def __init__(self):
        super().__init__("1/s")
        self.add_input("in")
        self.add_output("out")
        self.add_param("InitialCondition", 0.0)
        self.state = np.array([0.0])
        self.initialized = False

    def compute(self, t, dt):
        if not self.initialized:
            self.state[0] = float(self.params["InitialCondition"])
            self.initialized = True
        self.outputs["out"].value = self.state[0]

    def update_state(self, t, dt):
        derivative = self.inputs["in"].value
        self.state[0] += derivative * dt

    def reset(self):
        self.initialized = False

    def get_editor_dialog(self, parent=None):
        """Return generic parameter editor dialog."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Edit {self.name}")
        layout = QFormLayout(dialog)
        widgets = {}

        for key, val in self.params.items():
            le = QLineEdit(str(val))
            layout.addRow(key, le)
            widgets[key] = le

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            for key, le in widgets.items():
                old_val = self.params[key]
                new_str = le.text()
                try:
                    if isinstance(old_val, float) or isinstance(old_val, int):
                        self.params[key] = float(new_str)
                    else:
                        self.params[key] = new_str
                except:
                    self.params[key] = new_str
            original_accept()

        dialog.accept = accept_with_save
        return dialog
