from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QMessageBox

class SimulationSettingsDialog(QDialog):
    """Dialog to set Simulation Duration, Time Step, and Solver."""
    def __init__(self, parent=None, current_duration=10.0, current_dt=0.01, current_solver="euler"):
        super().__init__(parent)
        self.setWindowTitle("Simulation Settings")
        self.resize(300, 170)

        layout = QFormLayout(self)

        self.dur_edit = QLineEdit(str(current_duration))
        self.dt_edit = QLineEdit(str(current_dt))

        layout.addRow("Duration (s):", self.dur_edit)
        layout.addRow("Time Step (s):", self.dt_edit)

        self.solver_combo = QComboBox()
        self.solver_combo.addItem("Euler (fixed-step)", "euler")
        self.solver_combo.addItem("RK4 (Runge-Kutta 4)", "rk4")
        idx = self.solver_combo.findData(current_solver)
        self.solver_combo.setCurrentIndex(idx if idx >= 0 else 0)
        layout.addRow("Solver:", self.solver_combo)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addRow(btns)

    def accept(self):
        """Validate before closing -- reject bad input with an explanation
        and keep the dialog open, instead of silently discarding it and
        closing anyway (get_values() would return (None, None) and the
        caller would just leave the old settings in place with no
        indication why)."""
        dur, dt = self._parse_values()
        if dur is None:
            QMessageBox.warning(
                self, "Invalid Settings",
                "Duration and Time Step must both be positive numbers."
            )
            return
        super().accept()

    def _parse_values(self):
        try:
            dur = float(self.dur_edit.text())
            dt = float(self.dt_edit.text())
            if dt <= 0 or dur <= 0:
                return None, None
            return dur, dt
        except ValueError:
            return None, None

    def get_values(self):
        return self._parse_values()

    def get_solver(self):
        return self.solver_combo.currentData()
