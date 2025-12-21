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
        self._cached_ic = 0.0
        
        # Set a nice label
        self.name = "∫"
        self._cache_params()

    def _cache_params(self):
        try:
            self._cached_ic = float(self.params.get("InitialCondition", 0.0))
        except:
            self._cached_ic = 0.0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        # 1. Initialization Logic
        if not self.initialized:
            self.state = self._cached_ic
            self.initialized = True

        # 2. Set the Output
        self.outputs["out"].value = self.state

    def update_state(self, t, dt, context=None):
        # Perform the integration (Euler: New = Old + Input * TimeStep)
        inp = self.inputs["in"].value if "in" in self.inputs else 0.0
        self.state += float(inp) * dt

    def reset(self):
        """Reset state to Initial Condition on stop/start."""
        self.initialized = False
        self.state = self._cached_ic

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