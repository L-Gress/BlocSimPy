from ..models import BlockModel

class RelationalOperator(BlockModel):
    """
    Relational Operator Block.
    Compares two inputs (A and B) based on the selected operator.
    Output is 1.0 if True, 0.0 if False.
    """
    
    BLOCK_INFO = {
        "description": "Performs relational operations on input signals",
        "parameters": "Operator (>, <, >=, <=, ==, !=)",
        "formula": "Outputs 1.0 or 0.0 based on comparison",
        "usage": "Compare values",
        "category": "Logic"
    }
    
    def __init__(self):
        super().__init__("Relational")
        self.add_input("in1") # Operand A
        self.add_input("in2") # Operand B
        self.add_output("out")
        
        # Default operator
        self.add_param("Operator", ">")
        
        self._update_label()

    def _update_label(self):
        """Updates the block name to show the operator symbol."""
        op = self.params.get("Operator", ">")
        # Visual improvement: Display as comparison
        self.name = op

    def compute(self, t, dt, context=None):
        # 1. Get Inputs (default to 0.0)
        val_a = self.inputs["in1"].value if "in1" in self.inputs else 0.0
        val_b = self.inputs["in2"].value if "in2" in self.inputs else 0.0
        
        op = self.params.get("Operator", ">")
        result = False

        # 2. Perform Logic
        if op == ">":
            result = val_a > val_b
        elif op == "<":
            result = val_a < val_b
        elif op == ">=":
            result = val_a >= val_b
        elif op == "<=":
            result = val_a <= val_b
        elif op == "==":
            result = val_a == val_b
        elif op == "!=":
            result = val_a != val_b
            
        # 3. Output 1.0 or 0.0
        self.outputs["out"].value = 1.0 if result else 0.0

    def compute_chunk(self, t_vec, dt, context=None):
        val_a = self.inputs["in1"].vector_value
        val_b = self.inputs["in2"].vector_value
        
        op = self.params.get("Operator", ">")
        result = None
        
        if op == ">":
            result = val_a > val_b
        elif op == "<":
            result = val_a < val_b
        elif op == ">=":
            result = val_a >= val_b
        elif op == "<=":
            result = val_a <= val_b
        elif op == "==":
            result = val_a == val_b
        elif op == "!=":
            result = val_a != val_b
            
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
        dialog.setWindowTitle("Edit Relational Operator")
        layout = QFormLayout(dialog)
        
        # Create Dropdown for operators
        combo = QComboBox()
        options = [">", "<", ">=", "<=", "==", "!="]
        combo.addItems(options)
        
        # Select currently active operator
        current_op = self.params.get("Operator", ">")
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
            # Save the text from the dropdown (e.g., ">=")
            self.params["Operator"] = combo.currentText()
            
            # Update label immediately
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog
