from ..models import BlockModel
from ..variables import display_value

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
        self.name = display_value(self.params.get("Value", 1.0))

    def compute(self, t, dt, context=None):
        self.outputs["out"].value = self._cached_value

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
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        from gui.widgets.param_value_editor import make_row_editor, row_editor_value, PARSE_ERROR

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Edit {self.name}")
        layout = QFormLayout(dialog)
        widgets = {}

        for key, val in self.params.items():
            editor = make_row_editor(key, val)
            layout.addRow(key, editor)
            widgets[key] = editor

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            for key, editor in widgets.items():
                value = row_editor_value(editor)
                if value is not PARSE_ERROR:
                    self.params[key] = value

            # Update label and refresh the cached value on manual edit
            self._update_label()
            self._cache_params()
            original_accept()

        dialog.accept = accept_with_save
        return dialog