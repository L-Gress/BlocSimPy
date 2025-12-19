from ..models import BlockModel
from .rest_input import RestIODialog # Reuse the dialog

class RestOutput(BlockModel):
    BLOCK_INFO = {
        "description": "Exposes a value to the REST API for external monitoring",
        "parameters": "Endpoint ID, Data Type",
        "formula": "API_Value = Input",
        "usage": "Use to monitor simulation state from external dashboards or applications.",
        "category": "IO"
    }

    def __init__(self):
        super().__init__("RestOutput")
        self.add_param("Endpoint ID", "output1")
        self.add_param("Data Type", "float") 
        self.add_input("in")
        self.last_value = 0.0

    def compute(self, time, dt):
        # We store the raw value, typing happens on read/get if needed, 
        # but generally ports carry generic values.
        # However, for consistency we might want to cast it here or in get_value
        val = self.inputs["in"].value
        self.last_value = val
        
    def get_value(self):
        # Cast to configured type for consistency
        dtype = self.params.get("Data Type", "float")
        try:
            if dtype == "int":
                return int(self.last_value)
            elif dtype == "str":
                return str(self.last_value)
            elif dtype == "bool":
                return bool(self.last_value)
            else:
                return float(self.last_value)
        except:
            return self.last_value

    def register_api_routes(self):
        """
        Returns a dict of relative_path -> handler_object.
        """
        eid = self.params.get("Endpoint ID", "output1")
        return {
            f"outputs/{eid}": self
        }

    def handle_get(self):
        """Handle incoming GET request."""
        return {"value": self.get_value()}

    def get_editor_dialog(self, parent=None):
        return RestIODialog(self.params, parent=parent)
