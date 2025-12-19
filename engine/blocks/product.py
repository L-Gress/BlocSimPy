from ..models import BlockModel

# ==========================================
# PRODUCT BLOCK (Multiplication)
# ==========================================
class Product(BlockModel):
    """
    Product Block.
    Multiplies two inputs: out = in1 * in2
    """
    
    BLOCK_INFO = {
        "description": "Multiplies input signals element-wise",
        "parameters": "None (takes 2 inputs)",
        "formula": "Output = in1 × in2",
        "usage": "Multiply signals, modulate, or implement nonlinear operations",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Product")
        self.add_input("in1")
        self.add_input("in2")
        self.add_output("out")
        
        # Set the display name to the math symbol
        self.name = "×"

    def compute(self, t, dt):
        # Default to 0.0 if not connected
        v1 = self.inputs["in1"].value if "in1" in self.inputs else 0.0
        v2 = self.inputs["in2"].value if "in2" in self.inputs else 0.0
        
        self.outputs["out"].value = v1 * v2

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Product Info")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Multiplies two signals.\nNo parameters."))
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok)
        btns.accepted.connect(dialog.accept)
        layout.addWidget(btns)
        return dialog