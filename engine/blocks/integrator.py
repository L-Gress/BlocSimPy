from ..models import BlockModel

class Integrator(BlockModel):
    """Integrator block - integrates signal over time."""
    
    BLOCK_INFO = {
        "description": "Integrates input signal over time (Euler method)",
        "parameters": "Initial Condition",
        "formula": "Standard recursive integration",
        "usage": "Dynamic systems, state estimation",
        "category": "Signal"
    }
    
    def __init__(self):
        super().__init__("Integrator")
        self.add_input("in")
        self.add_output("out")
        self.add_param("InitialCondition", 0.0)
        
        self.state = 0.0
        self.initialized = False
        
        # Set a nice label
        self.name = "∫"

    def compute(self, t, dt):
        # 1. Initialization Logic
        if not self.initialized:
            try:
                self.state = float(self.params["InitialCondition"])
            except:
                self.state = 0.0
            self.initialized = True

        # 2. Set the Output (Send current memory to the wire)
        self.outputs["out"].value = self.state

        # 3. Calculate the State for the NEXT loop (The fix!)
        # Check if input is connected
        inp = 0.0
        if "in" in self.inputs:
            inp = float(self.inputs["in"].value)
            
        # Perform the integration (Euler: New = Old + Input * TimeStep)
        self.state += inp * dt

    def reset(self):
        """Reset state to Initial Condition on stop/start."""
        self.initialized = False
        try:
            self.state = float(self.params.get("InitialCondition", 0.0))
        except:
            self.state = 0.0

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Integrator")
        layout = QFormLayout(dialog)
        
        # Initial Condition Input
        val = self.params.get("InitialCondition", 0.0)
        le = QLineEdit(str(val))
        layout.addRow("Initial Condition:", le)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            try:
                self.params["InitialCondition"] = float(le.text())
            except ValueError:
                self.params["InitialCondition"] = 0.0
            
            # Reset immediately so the change takes effect if simulation is stopped
            self.reset()
            original_accept()

        dialog.accept = accept_with_save
        return dialog