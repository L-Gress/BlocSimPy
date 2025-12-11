from ..models import BlockModel

class Max(BlockModel):
    """
    Max Block.
    Returns the larger of two inputs: out = max(in1, in2)
    """
    
    BLOCK_INFO = {
        "description": "Outputs the larger value of the two input signals",
        "parameters": "None (takes 2 inputs)",
        "formula": "Output = max(in1, in2)",
        "usage": "Signal limiting, logic comparison, or ceiling functions"
    }
    
    def __init__(self):
        super().__init__("Max")
        self.add_input("in1")
        self.add_input("in2")
        self.add_output("out")
        
        # Set the display name
        self.name = "Max"

    def compute(self, t, dt):
        # Default to 0.0 if not connected
        v1 = self.inputs["in1"].value if "in1" in self.inputs else 0.0
        v2 = self.inputs["in2"].value if "in2" in self.inputs else 0.0
        
        self.outputs["out"].value = max(v1, v2)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Max Info")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Returns the maximum of two signals.\nNo parameters."))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dialog.accept)
        layout.addWidget(btns)
        return dialog