from ..models import BlockModel

class Divide(BlockModel):
    """
    Divide Block.
    Divides two inputs: out = num / den
    """
    
    BLOCK_INFO = {
        "description": "Divides first input by second input",
        "parameters": "None (takes 2 inputs)",
        "formula": "Output = num / den",
        "usage": "Normalize signals, calculate ratios, or implement inverse operations"
    }
    
    def __init__(self):
        super().__init__("Divide")
        self.add_input("num")
        self.add_input("den")
        self.add_output("out")
        
        # Set the display name to the math symbol
        self.name = "÷"

    def compute(self, t, dt):
        # Default to 0.0 if not connected
        v1 = self.inputs["num"].value if "num" in self.inputs else 0.0
        v2 = self.inputs["den"].value if "den" in self.inputs else 0.0
        
        # Avoid division by zero
        if v2 != 0.0:
            self.outputs["out"].value = v1 / v2
        else:
            self.outputs["out"].value = 0.0  # or some defined behavior for division by zero

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Divide Info")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Divides two signals.\nNo parameters."))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dialog.accept)
        layout.addWidget(btns)
        return dialog