from ..models import BlockModel

# ==========================================
# 1. INPUT PORT (Inside SubGraph)
# ==========================================
class InputPort(BlockModel):
    """Input port for SubGraphs."""
    
    BLOCK_INFO = {
        "description": "Creates external input port for SubGraphs",
        "parameters": "PortName",
        "formula": "For Subsystems: Passes data from outside to inside",
        "usage": "Place inside a SubSystem to create an external input pin",
        "category": "Structure"
    }
    
    def __init__(self):
        super().__init__("InputPort")
        self.add_output("out")
        self.add_param("PortName", "In1")
        self.is_subsystem_input = True # Flag for the container
        self._update_label()

    def _update_label(self):
        self.name = f"In: {self.params.get('PortName', 'In1')}"

    def compute(self, t, dt, context=None):
        # Value is injected by the SubSystem container before this runs
        pass

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Input Port")
        layout = QFormLayout(dialog)
        
        name_edit = QLineEdit(str(self.params.get("PortName", "In1")))
        layout.addRow("Port Name:", name_edit)
        
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        
        # --- FIX START ---
        # 1. Capture the original Qt accept method
        original_accept = dialog.accept
        
        # 2. Define your wrapper
        def accept_with_save():
            self.params["PortName"] = name_edit.text()
            self._update_label()
            # 3. Call the ORIGINAL method, not dialog.accept()
            original_accept()
            
        # 4. Overwrite
        dialog.accept = accept_with_save
        # --- FIX END ---
        
        return dialog
