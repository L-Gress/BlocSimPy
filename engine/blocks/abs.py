from ..models import BlockModel
import numpy as np
from PySide6.QtWidgets import QMessageBox

class Abs(BlockModel):
    """
    Absolute Value Block.
    Outputs the non-negative value of the input.
    """
    
    BLOCK_INFO = {
        "description": "Computes the absolute value of the signal",
        "parameters": "None",
        "formula": "Output = |Input|",
        "usage": "Use for Full-Wave Rectification or magnitude calculation.",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Abs")
        self.add_input("in")
        self.add_output("out")
        
    def compute(self, t, dt, context=None):
        inp = self.inputs["in"].value
        self.outputs["out"].value = np.abs(inp)

    def compute_chunk(self, t_vec, dt, context=None):
        inp = self.inputs["in"].vector_value
        self.outputs["out"].vector_value = np.abs(inp)

    def get_editor_dialog(self, parent=None):
        # No parameters to edit, so we return None or show a simple info message
        return None