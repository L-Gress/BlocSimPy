from ..models import BlockModel

class RestInput(BlockModel):
    BLOCK_INFO = {
        "category": "IO",
        "doc": "Receives a value from the REST API."
    }

    def __init__(self):
        super().__init__("RestInput")
        # Parameter to identify this input in the API
        self.add_param("Endpoint ID", "input1")
        self.add_param("Initial Value", 0.0)
        self.add_param("Data Type", "float") # float, int, str, bool
        self.add_output("out")
        self.current_value = 0.0

    def reset(self):
        try:
            val = self.params.get("Initial Value", 0.0)
            self._set_value_with_type(val)
        except ValueError:
            self.current_value = 0.0

    def compute(self, time, dt):
        self.outputs["out"].value = self.current_value
        
    def _set_value_with_type(self, value):
        dtype = self.params.get("Data Type", "float")
        try:
            if dtype == "int":
                self.current_value = int(float(value)) # Handles "1.0"
            elif dtype == "str":
                self.current_value = str(value)
            elif dtype == "bool":
                if isinstance(value, str):
                    self.current_value = value.lower() in ["true", "1", "yes"]
                else:
                    self.current_value = bool(value)
            else: # float is default
                self.current_value = float(value)
        except:
             # Fallback
             self.current_value = float(value) if dtype == "float" else value

    def set_value(self, value):
        self._set_value_with_type(value)

    def register_api_routes(self):
        """
        Returns a dict of relative_path -> handler_object.
        The server will route /api/deployments/{id}/{relative_path} to this block.
        """
        eid = self.params.get("Endpoint ID", "input1")
        return {
            f"inputs/{eid}": self
        }

    def handle_post(self, data):
        """Handle incoming POST data."""
        value = data.get("value")
        if value is None:
            raise ValueError("Field 'value' is required")
        self.set_value(value)
        return {"message": "Value updated", "value": self.current_value}

    def get_editor_dialog(self, parent=None):
        return RestIODialog(self.params, parent=parent)

from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QComboBox, QDialogButtonBox, QVBoxLayout 

class RestIODialog(QDialog):
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params
        self.setWindowTitle("REST I/O Configuration")
        
        layout = QVBoxLayout(self)
        form = QFormLayout()
        
        self.eid_edit = QLineEdit(str(self.params.get("Endpoint ID", "")))
        form.addRow("Endpoint ID:", self.eid_edit)
        
        self.dtype_combo = QComboBox()
        self.dtype_combo.addItems(["float", "int", "str", "bool"])
        curr_type = str(self.params.get("Data Type", "float"))
        self.dtype_combo.setCurrentText(curr_type)
        form.addRow("Data Type:", self.dtype_combo)

        # Show Initial Value only if applicable (RestInput has it)
        if "Initial Value" in self.params:
             self.init_val_edit = QLineEdit(str(self.params.get("Initial Value", "")))
             form.addRow("Initial Value:", self.init_val_edit)
        
        layout.addLayout(form)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)
        
    def accept(self):
        self.params["Endpoint ID"] = self.eid_edit.text()
        self.params["Data Type"] = self.dtype_combo.currentText()
        if hasattr(self, "init_val_edit"):
             self.params["Initial Value"] = self.init_val_edit.text()
        super().accept()
