from ..models import BlockModel
import numpy as np

class Min(BlockModel):
    """
    Min Block.
    Returns the smaller of two inputs: out = min(in1, in2)
    """
    
    BLOCK_INFO = {
        "description": "Outputs the smaller value of the two input signals",
        "parameters": "None (takes 2 inputs)",
        "formula": "Output = min(in1, in2)",
        "usage": "Signal clipping, logic comparison, or floor functions",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Min")
        self.add_input("in1")
        self.add_input("in2")
        self.add_output("out")
        
        # Set the display name
        self.name = "Min"

    def compute(self, t, dt, context=None):
        # Default to 0.0 if not connected
        v1 = self.inputs["in1"].value if "in1" in self.inputs else 0.0
        v2 = self.inputs["in2"].value if "in2" in self.inputs else 0.0
        
        self.outputs["out"].value = min(v1, v2)

    def compute_chunk(self, t_vec, dt, context=None):
        v1 = self.inputs["in1"].vector_value
        v2 = self.inputs["in2"].vector_value
        self.outputs["out"].vector_value = np.minimum(v1, v2)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Min Info")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Returns the minimum of two signals.\nNo parameters."))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dialog.accept)
        layout.addWidget(btns)
        return dialog