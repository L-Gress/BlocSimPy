from ..models import BlockModel

class Switch(BlockModel):
    """Switches between two inputs based on a control threshold."""
    
    BLOCK_INFO = {
        "description": "Passes Input 1 or Input 2 based on the control signal value",
        "parameters": "Threshold",
        "formula": "Output = in1 if ctrl >= Threshold else in2",
        "usage": "Conditional routing, mode switching, or redundancy",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("Switch")
        self.add_input("in1") # Top
        self.add_input("ctrl") # Middle
        self.add_input("in2") # Bottom
        self.add_output("out")
        self.add_param("Threshold", 0.5)
        self._cache_params()

    def _cache_params(self):
        try:
            self._threshold = float(self.params.get("Threshold", 0.5))
        except:
            self._threshold = 0.5

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        ctrl = self.inputs["ctrl"].value
        if ctrl >= self._threshold:
            self.outputs["out"].value = self.inputs["in1"].value
        else:
            self.outputs["out"].value = self.inputs["in2"].value

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Switch")
        layout = QFormLayout(dialog)
        le_th = QLineEdit(str(self.params.get("Threshold", 0.5)))
        layout.addRow("Threshold:", le_th)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        def save():
            try:
                self.params["Threshold"] = float(le_th.text())
                self._cache_params()
            except: pass
        dialog.accepted.connect(save)
        return dialog
