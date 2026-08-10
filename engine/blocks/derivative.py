from ..models import BlockModel

class Derivative(BlockModel):
    """Calculates the discrete-time derivative of the input signal."""
    
    BLOCK_INFO = {
        "description": "Calculates the rate of change of the input signal (du/dt)",
        "parameters": "None",
        "formula": "Output = (u[k] - u[k-1]) / dt",
        "usage": "Extract velocity from position, implement PD controllers, or detect signal changes",
        "category": "Signal"
    }
    
    def __init__(self):
        super().__init__("Derivative")
        self.add_input("in")
        self.add_output("out")
        self.last_input = 0.0
        self.initialized = False

    def reset(self):
        self.initialized = False

    def compute(self, t, dt, context=None):
        u = self.inputs["in"].value
        if not self.initialized:
            self.last_input = u
            self.initialized = True
            self.outputs["out"].value = 0.0
            return
            
        if dt > 0:
            res = (u - self.last_input) / dt
        else:
            res = 0.0
            
        self.outputs["out"].value = float(res)
        self.last_input = u

    def get_editor_dialog(self, parent=None):
        return None
