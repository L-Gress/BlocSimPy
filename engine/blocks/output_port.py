from ..models import BlockModel

class OutputPort(BlockModel):
    """Output port for SubGraphs."""
    
    BLOCK_INFO = {
        "description": "Creates external output port for SubGraphs",
        "parameters": "PortName",
        "formula": "For Subsystems: Passes data from inside to outside",
        "usage": "Place inside a SubSystem to create an external output pin",
        "category": "Structure"
    }
    
    def __init__(self):
        super().__init__("OutputPort")
        self.add_input("in")
        self.add_param("PortName", "Out1")
        self.is_subsystem_output = True
        self._update_label()

    def _update_label(self):
        self.name = f"Out: {self.params.get('PortName', 'Out1')}"

    def compute(self, t, dt, context=None):
        # Pass-through. SubSystem reads self.inputs['in'] after this runs.
        pass

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Output Port")
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit(str(self.params.get("PortName", "Out1")))
        layout.addRow("Port Name:", name_edit)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        # --- FIX ---
        original_accept = dialog.accept 

        def accept_with_save():
            self.params["PortName"] = name_edit.text()
            self._update_label()
            original_accept() # Call the captured variable
            
        dialog.accept = accept_with_save
        # -----------
        
        return dialog