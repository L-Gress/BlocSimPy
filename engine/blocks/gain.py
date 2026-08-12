from ..models import BlockModel
from ..variables import display_value

class Gain(BlockModel):
    """Gain block - multiplies input by a constant factor."""
    
    BLOCK_INFO = {
        "description": "Multiplies input signal by a constant gain factor",
        "parameters": "Gain (multiplication factor)",
        "formula": "out = Gain * in",
        "usage": "Scaling signals",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Gain")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Gain", 1.0)
        
        self._cached_gain = 1.0
        self._update_label()
        self._cache_params()

    def _cache_params(self):
        try:
            self._cached_gain = float(self.params.get("Gain", 1.0))
        except:
            self._cached_gain = 0.0

    def _update_label(self):
        """Format the name based on the current gain value."""
        self.name = f"K = {display_value(self.params.get('Gain', 1.0))}"

    def compute(self, t, dt, context=None):
        u = self.inputs["in"].value if "in" in self.inputs else 0.0
        self.outputs["out"].value = u * self._cached_gain

    # --- FIX 1: Catch when the params dictionary is replaced (e.g., JSON load) ---
    def __setattr__(self, name, value):
        # Perform the standard assignment
        super().__setattr__(name, value)
        
        # If the 'params' dictionary was just overwritten, update the label and cache
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()
            self._cache_params()

    # --- FIX 2: Catch when the object is loaded via Pickle ---
    def __setstate__(self, state):
        # Restore state
        self.__dict__.update(state)
        # Update label and cache immediately after load
        self._update_label()
        self._cache_params()

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QDialogButtonBox
        from gui.widgets.param_value_editor import make_row_editor, row_editor_value, PARSE_ERROR

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Gain")
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

            # Update label and refresh the cached gain on manual edit
            self._update_label()
            self._cache_params()
            original_accept()

        dialog.accept = accept_with_save
        return dialog