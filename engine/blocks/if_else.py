from ..models import BlockModel

class IfElse(BlockModel):
    """
    Switch / If-Else Block.
    
    Inputs:
    1. cond  : The condition signal.
    2. true  : The value to pass if (cond >= threshold).
    3. false : The value to pass if (cond < threshold).
    
    Output:
    - out    : The selected signal.
    """
    def __init__(self):
        super().__init__("If / Else")
        
        # Define Inputs
        self.add_input("cond")   # Top input
        self.add_input("true")   # Middle input
        self.add_input("false")  # Bottom input
        
        # Define Output
        self.add_output("out")
        
        # Threshold parameter (default 0.5, similar to standard digital logic checks)
        self.add_param("Threshold", 0.5)
        
        # Update label to show the logic
        self._update_label()

    def _update_label(self):
        """Updates the block name to show the logic condition."""
        try:
            thresh = float(self.params["Threshold"])
            # Format integer thresholds cleanly (e.g. "0" instead of "0.0")
            s_thresh = str(int(thresh)) if thresh.is_integer() else str(thresh)
            self.name = f"if cond ≥ {s_thresh}"
        except:
            self.name = "If / Else"

    def compute(self, t, dt):
        # Get Threshold
        try:
            threshold = float(self.params["Threshold"])
        except ValueError:
            threshold = 0.5

        # Get Inputs (default to 0.0 if not connected)
        cond = self.inputs["cond"].value if "cond" in self.inputs else 0.0
        val_true = self.inputs["true"].value if "true" in self.inputs else 0.0
        val_false = self.inputs["false"].value if "false" in self.inputs else 0.0

        # Logic
        if cond >= threshold:
            self.outputs["out"].value = val_true
        else:
            self.outputs["out"].value = val_false

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit If/Else Threshold")
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
                try:
                    self.params[key] = float(le.text())
                except ValueError:
                    self.params[key] = le.text()
            
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog