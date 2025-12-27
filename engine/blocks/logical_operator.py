from ..models import BlockModel

class LogicalOperator(BlockModel):
    """
    Logical Operator Block.
    Performs logical operations (AND, OR, NOT, etc) on inputs.
    Output is 1.0 if True, 0.0 if False.
    """
    
    BLOCK_INFO = {
        "description": "Performs logical operations on input signals",
        "parameters": "Operator (AND, OR, NOT, XOR, NAND, NOR)",
        "formula": "Outputs 1.0 or 0.0 based on logical operation",
        "usage": "Combine boolean conditions",
        "category": "Logic"
    }
    
    def __init__(self):
        super().__init__("Logical")
        self.add_input("in1") # Operand A
        self.add_input("in2") # Operand B (Ignored for NOT)
        self.add_output("out")
        
        # Default operator
        self.add_param("Operator", "AND")
        
        self._update_label()

    def _update_label(self):
        """Updates the block name to show the operator symbol."""
        op = self.params.get("Operator", "AND")
        self.name = op

    def compute(self, t, dt, context=None):
        # 1. Get Inputs
        # We treat any non-zero value as True, and 0.0 as False.
        # This is standard Python boolean truthiness for floats.
        val_a = self.inputs["in1"].value if "in1" in self.inputs else 0.0
        val_b = self.inputs["in2"].value if "in2" in self.inputs else 0.0
        
        bool_a = bool(val_a)
        bool_b = bool(val_b)
        
        op = self.params.get("Operator", "AND")
        result = False

        if op == "AND":
            result = bool_a and bool_b
        elif op == "OR":
            result = bool_a or bool_b
        elif op == "NOT":
            result = not bool_a
        elif op == "XOR":
            result = bool_a != bool_b
        elif op == "NAND":
            result = not (bool_a and bool_b)
        elif op == "NOR":
            result = not (bool_a or bool_b)
            
        # Output 1.0 or 0.0
        self.outputs["out"].value = 1.0 if result else 0.0

    def compute_chunk(self, t_vec, dt, context=None):
        import numpy as np
        # 1. Get Inputs (Vectorized)
        val_a = self.inputs["in1"].vector_value
        val_b = self.inputs["in2"].vector_value
        
        # Convert to boolean (element-wise check if not zero)
        bool_a = val_a != 0.0
        bool_b = val_b != 0.0
        
        op = self.params.get("Operator", "AND")
        result = None
        
        if op == "AND":
            result = np.logical_and(bool_a, bool_b)
        elif op == "OR":
            result = np.logical_or(bool_a, bool_b)
        elif op == "NOT":
            result = np.logical_not(bool_a)
        elif op == "XOR":
            result = np.logical_xor(bool_a, bool_b)
        elif op == "NAND":
            result = np.logical_not(np.logical_and(bool_a, bool_b))
        elif op == "NOR":
            result = np.logical_not(np.logical_or(bool_a, bool_b))
            
        # Convert boolean array to float (1.0 or 0.0)
        if result is not None:
            self.outputs["out"].vector_value = result.astype(float)
        else:
            self.outputs["out"].vector_value.fill(0.0)

    # --- Safety hooks for loading files ---
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._update_label()
    # --------------------------------------

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QComboBox, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Logical Operator")
        layout = QFormLayout(dialog)
        
        # Create Dropdown for operators
        combo = QComboBox()
        options = ["AND", "OR", "NOT", "XOR", "NAND", "NOR"]
        combo.addItems(options)
        
        # Select currently active operator
        current_op = self.params.get("Operator", "AND")
        index = combo.findText(current_op)
        if index >= 0:
            combo.setCurrentIndex(index)

        layout.addRow("Operator:", combo)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            # Save the text from the dropdown
            self.params["Operator"] = combo.currentText()
            
            # Update label immediately
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog
