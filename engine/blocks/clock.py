from ..models import BlockModel

class Clock(BlockModel):
    """
    Clock Source Block.
    Outputs the current simulation time (t) in seconds.
    """
    
    BLOCK_INFO = {
        "description": "Outputs current simulation time",
        "parameters": "None",
        "formula": "Output = t (simulation time)",
        "usage": "Time-dependent logic, scheduling, or time-varying systems"
    }
    
    def __init__(self):
        super().__init__("Clock")
        # No inputs, as this is a source
        # One output named 't' (or 'out')
        self.add_output("out")

    def compute(self, t, dt):
        """
        Called at every simulation step.
        t: current simulation time
        dt: time step size
        """
        # Simply pass the current time to the output
        self.outputs["out"].value = float(t)

    def get_editor_dialog(self, parent=None):
        """
        Simple information dialog since there are no parameters.
        """
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle("Clock Block")
        layout = QVBoxLayout(dialog)

        info = QLabel("Outputs the current simulation time in seconds.\nNo parameters to configure.")
        layout.addWidget(info)

        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dialog.accept)
        layout.addWidget(btns)

        return dialog