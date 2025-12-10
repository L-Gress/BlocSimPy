from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

class SimulationSettingsDialog(QDialog):
    """Dialog to set Simulation Duration and Time Step."""
    def __init__(self, parent=None, current_duration=10.0, current_dt=0.01):
        super().__init__(parent)
        self.setWindowTitle("Simulation Settings")
        self.resize(300, 150)

        layout = QFormLayout(self)

        self.dur_edit = QLineEdit(str(current_duration))
        self.dt_edit = QLineEdit(str(current_dt))

        layout.addRow("Duration (s):", self.dur_edit)
        layout.addRow("Time Step (s):", self.dt_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def get_values(self):
        try:
            dur = float(self.dur_edit.text())
            dt = float(self.dt_edit.text())
            if dt <= 0 or dur <= 0:
                raise ValueError("Values must be positive")
            return dur, dt
        except ValueError:
            return None, None
