from ..models import BlockModel
import numpy as np

class Modulo(BlockModel):
    """
    Modulo Block.
    Computes the remainder of division: out = in % mod
    """
    
    BLOCK_INFO = {
        "description": "Computes remainder of division",
        "parameters": "None (takes 2 inputs)",
        "formula": "Output = in % mod",
        "usage": "Generate periodic ramps, wrap values, or simple clock dividers",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Modulo")
        self.add_input("in")
        self.add_input("mod")
        self.add_output("out")
        
        # Set the display name
        self.name = "%"

    def compute(self, t, dt, context=None):
        # Default to 0.0 if not connected
        v_in = self.inputs["in"].value if "in" in self.inputs else 0.0
        v_mod = self.inputs["mod"].value if "mod" in self.inputs else 1.0 # Default mod to 1 to avoid div0 if unconnected
        
        # Avoid division by zero
        if v_mod != 0.0:
            self.outputs["out"].value = v_in % v_mod
        else:
            self.outputs["out"].value = 0.0

    def compute_chunk(self, t_vec, dt, context=None):
        v_in = self.inputs["in"].vector_value
        v_mod = self.inputs["mod"].vector_value
        
        # NumPy handles modulus. We might want to avoid mod by zero if we care about warnings,
        # but standard Python behavior or NumPy behavior (return 0 or nan) is usually accepted in DSP.
        # We'll use errstate to silence warnings.
        with np.errstate(divide='ignore', invalid='ignore'):
             res = v_in % v_mod
             res[~np.isfinite(res)] = 0.0
             
        self.outputs["out"].vector_value = res

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Modulo Info")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Computes Remainder (Input % Modulus).\nNo parameters."))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dialog.accept)
        layout.addWidget(btns)
        return dialog
