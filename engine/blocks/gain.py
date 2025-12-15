from ..models import BlockModel

class Gain(BlockModel):
    """Gain block - multiplies input by a constant factor."""
    
    BLOCK_INFO = {
        "description": "Multiplies input signal by a constant gain factor",
        "parameters": "Gain (multiplication factor)",
        "formula": "out = Gain * in",
        "usage": "Scaling signals",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Gain")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Gain", 1.0)
        
        # Initial label update
        self._update_label()

    def _update_label(self):
        """Format the name based on the current gain value."""
        try:
            val = self.params.get("Gain", 1.0)   
            self.name = f"K = {val}"
        except:
            self.name = f"K = {self.params.get('Gain', '?')}"

    def compute(self, t, dt):
        try:
            g = float(self.params["Gain"])
        except:
            g = 0.0
        
        # Check if the label matches the actual parameter during simulation
        # This is a fallback self-correction
        expected_name_start = f"K = "
        if not self.name.startswith(expected_name_start):
             self._update_label()

        u = self.inputs["in"].value if "in" in self.inputs else 0.0
        self.outputs["out"].value = u * g

    # --- FIX 1: Catch when the params dictionary is replaced (e.g., JSON load) ---
    def __setattr__(self, name, value):
        # Perform the standard assignment
        super().__setattr__(name, value)
        
        # If the 'params' dictionary was just overwritten, update the label
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    # --- FIX 2: Catch when the object is loaded via Pickle ---
    def __setstate__(self, state):
        # Restore state
        self.__dict__.update(state)
        # Update label immediately after load
        self._update_label()

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Gain")
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
                new_str = le.text()
                try:
                    self.params[key] = float(new_str)
                except ValueError:
                    self.params[key] = new_str
            
            # Update label on manual edit
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog