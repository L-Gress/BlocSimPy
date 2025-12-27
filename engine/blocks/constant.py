from ..models import BlockModel

class Constant(BlockModel):
    """Outputs a constant value."""
    
    BLOCK_INFO = {
        "description": "Outputs a constant value throughout simulation",
        "parameters": "Value (constant number)",
        "formula": "Output = Value",
        "usage": "Provide setpoints, parameters, or fixed inputs to systems",
        "category": "Sources"
    }
    
    def __init__(self):
        super().__init__("Constant")
        self.add_output("out")
        self.add_param("Value", 1.0)
        
        self._cached_value = 1.0
        self._update_label()
        self._cache_params()

    def _cache_params(self):
        try:
            self._cached_value = float(self.params.get("Value", 1.0))
        except:
            self._cached_value = 0.0

    def _update_label(self):
        """Format the name based on the current constant value."""
        try:
            val = self.params.get("Value", 1.0)
            self.name = f"{val}"
        except:
            self.name = f"{self.params.get('Value', '?')}"

    def compute(self, t, dt, context=None):
        self.outputs["out"].value = self._cached_value

    def compute_chunk(self, t_vec, dt, context=None):
        # Fill buffer with constant value
        self.outputs["out"].vector_value.fill(self._cached_value)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._update_label()
        self._cache_params()

    def get_editor_dialog(self, parent=None):
        """Return generic parameter editor dialog."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Edit {self.name}")
        layout = QFormLayout(dialog)
        widgets = {}

        for key, val in self.params.items():
            le = QLineEdit(str(val))
            layout.addRow(key, le)
            widgets[key] = le

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            for key, le in widgets.items():
                new_str = le.text()
                try:
                    # Try to convert to float, otherwise keep as string
                    self.params[key] = float(new_str)
                except ValueError:
                    self.params[key] = new_str
            
            # Update label on manual edit
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog