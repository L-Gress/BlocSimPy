from ..models import BlockModel
import numpy as np

class MathFunction(BlockModel):
    """Applies common mathematical functions to the input."""
    
    BLOCK_INFO = {
        "description": "Applies a selected mathematical function to the input signal",
        "parameters": "Function (Exp, Log, Log10, Sqrt, Abs, etc.)",
        "formula": "Output = func(Input)",
        "usage": "Linearization, scaling, or implementing advanced math models",
        "category": "Math"
    }
    
    def __init__(self):
        super().__init__("MathFunction")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Function", "Abs")
        self._cache_params()

    def _cache_params(self):
        self._func_name = self.params.get("Function", "Abs")
        
        # Function Map
        funcs = {
            "Abs": np.abs,
            "Exp": np.exp,
            "Log": np.log,
            "Log10": np.log10,
            "Sqrt": np.sqrt,
            "Square": np.square,
            "Sin": np.sin,
            "Cos": np.cos,
            "Tan": np.tan,
            "Asin": np.arcsin,
            "Acos": np.arccos,
            "Atan": np.arctan,
            "Floor": np.floor,
            "Ceil": np.ceil,
        }
        self._func = funcs.get(self._func_name, np.abs)

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        try:
            val = self.inputs["in"].value
            res = self._func(val)
            self.outputs["out"].value = float(res)
        except:
            self.outputs["out"].value = 0.0

    def compute_chunk(self, t_vec, dt, context=None):
        # self._func is mapped to NumPy functions (np.abs, np.sin, etc)
        # so it inherently supports vectors.
        val = self.inputs["in"].vector_value
        try:
            self.outputs["out"].vector_value = self._func(val)
        except:
            self.outputs["out"].vector_value.fill(0.0)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QComboBox, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Math Function")
        layout = QFormLayout(dialog)
        
        combo = QComboBox()
        funcs = ["Abs", "Exp", "Log", "Log10", "Sqrt", "Square", "Sin", "Cos", "Tan", "Asin", "Acos", "Atan", "Floor", "Ceil"]
        combo.addItems(funcs)
        combo.setCurrentText(self.params.get("Function", "Abs"))
        layout.addRow("Function:", combo)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        def save():
            self.params["Function"] = combo.currentText()
            self._cache_params()
        dialog.accepted.connect(save)
        return dialog
