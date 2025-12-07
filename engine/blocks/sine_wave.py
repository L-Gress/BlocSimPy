from ..models import BlockModel
import numpy as np


class SineWave(BlockModel):
    def __init__(self):
        super().__init__("SineWave")
        self.add_output("out")
        self.add_param("Amplitude", 1.0)
        self.add_param("Frequency", 1.0)

    def compute(self, t, dt):
        amp = float(self.params["Amplitude"])
        freq = float(self.params["Frequency"])
        self.outputs["out"].value = amp * np.sin(2 * np.pi * freq * t)

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
