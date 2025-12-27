from ..models import BlockModel


class Sum(BlockModel):
    """Sum block - adds or subtracts signals."""
    
    BLOCK_INFO = {
        "description": "Adds or subtracts two input signals",
        "parameters": "None (takes 2 inputs)",
        "formula": "Output = in1 + in2",
        "usage": "Combine signals, implement feedback loops, or calculate errors",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Sum")
        self.add_input("in1")
        self.add_input("in2")
        self.add_output("out")

    def compute(self, t, dt, context=None):
        v1 = self.inputs["in1"].value 
        v2 = self.inputs["in2"].value
        self.outputs["out"].value = v1 + v2

    def compute_chunk(self, t_vec, dt, context=None):
        v1 = self.inputs["in1"].vector_value
        v2 = self.inputs["in2"].vector_value
        self.outputs["out"].vector_value = v1 + v2

    def get_editor_dialog(self, parent=None):
        """Sum has no parameters, return None."""
        return None
