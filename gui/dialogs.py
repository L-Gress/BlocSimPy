from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QTextEdit, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


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


class HelpDialog(QDialog):
    """Simple help/about dialog describing the software and usage."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Help - BlocSimPy")
        self.resize(600, 380)

        layout = QVBoxLayout(self)

        intro = QLabel(
            "BlocSimPy — Block-based simulation editor.\n\n"
            "Usage:\n"
            "- Drag blocks from the Library into the scene.\n"
            "- Left-click and drag blocks to reposition.\n"
            "- Connect outputs to inputs by dragging from an output port to an input port.\n"
            "- Connections are orthogonal and can be adjusted by dragging their midpoint.\n"
            "- Double-click a block to edit its parameters.\n"
            "- Run simulations from the toolbar (set Duration and Time Step).\n"
            "- Save and Load graphs via the toolbar.\n\n"
            "Blocks included: SineWave, Gain, Sum, Integrator, LookupTable, Scope, Constant, TransferFunction.\n\n"
            "Formatting notes: TransferFunction and LookupTable editors accept comma-separated numbers."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        # Larger, scrollable details area (read-only)
        details = QTextEdit()
        details.setReadOnly(True)
        details.setPlainText(
            "Features:\n"
            " - Per-block parameter editors.\n"
            " - Orthogonal, draggable connections.\n"
            " - Library with search.\n"
            " - CSV import for LookupTable blocks.\n"
            " - TransferFunction block accepts numerator and denominator coefficients as comma-separated lists (e.g. '1, -0.3, 0.1').\n\n"
            "If you find issues or want enhancements, edit the source files under the `engine/` and `gui/` packages."
        )
        layout.addWidget(details)

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(self.accept)
        layout.addWidget(btns)
