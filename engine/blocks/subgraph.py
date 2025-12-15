from ..models import BlockModel

class SubGraph(BlockModel):
    """
    A container block that holds an internal graph.
    Renamed from SubSystem to SubGraph.
    """
    
    BLOCK_INFO = {
        "description": "Container block with custom interface/variables",
        "parameters": "BlockName + Custom Variables",
        "formula": "Executes internal diagram with variable substitution ($VarName)",
        "usage": "Double-click to enter. Ctrl+Double-click to edit variables. Use $VarName in internal blocks.",
        "category": "Structure"
    }
    
    def __init__(self):
        super().__init__("SubGraph")
        self.is_container = True
        
        # Use separate attributes to match scene_manager expectations
        self.internal_blocks_data = []
        self.internal_connections_data = []
        self.execution_blocks = []
        self.execution_map = {}
        
        # Default name parameter
        self.add_param("BlockName", "MySubGraph")
        
        # Initial label update
        self._update_label()

    def _update_label(self):
        """Formats the name to show Type on top, Name below."""
        user_name = self.params.get("BlockName", "MySubGraph")
        # The \n character forces a line break in QPainter.drawText
        self.name = f"SubGraph\n({user_name})"

    # Ensure label updates when parameters change (e.g. during loading)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._update_label()

    def sync_ports_from_data(self):
        """
        Reads internal_blocks_data to determine external inputs/outputs.
        """
        self.inputs.clear()
        self.outputs.clear()
        
        # Find InputPort and OutputPort blocks inside
        in_ports_data = sorted(
            [b for b in self.internal_blocks_data if b["type"] == "InputPort"],
            key=lambda x: x["params"].get("PortName", "")
        )
        out_ports_data = sorted(
            [b for b in self.internal_blocks_data if b["type"] == "OutputPort"],
            key=lambda x: x["params"].get("PortName", "")
        )

        for b_data in in_ports_data:
            name = b_data["params"].get("PortName", "In")
            self.add_input(name)
            
        for b_data in out_ports_data:
            name = b_data["params"].get("PortName", "Out")
            self.add_output(name)
    
    def refresh_io_ports(self):
        """Alias for sync_ports_from_data to match scene_manager expectations."""
        self.sync_ports_from_data()

    def reset(self):
        """Prepare internal blocks for simulation."""
        from . import BLOCK_REGISTRY
        
        self.execution_blocks = []
        self.execution_map = {}
        
        # Instantiate Internal Blocks
        
        # 0. Robustness: Scan for required variables that might be missing from params
        # This prevents crashes if the user forgot to define 'Amplitude' but used '$Amplitude'
        for b_data in self.internal_blocks_data:
            for p_val in b_data.get("params", {}).values():
                if isinstance(p_val, str) and p_val.strip().startswith("$"):
                    var_name = p_val.strip()[1:]
                    if var_name and var_name not in self.params:
                        # Auto-define with default 0.0
                        self.params[var_name] = 0.0

        for b_data in self.internal_blocks_data:
            b_type = b_data["type"]
            if b_type in BLOCK_REGISTRY:
                instance = BLOCK_REGISTRY[b_type]()
                instance.params = b_data["params"].copy()  # Copy to avoid mutating blueprint
                
                # Variable Substitution: Replace "$Var" with value from self.params
                for p_key, p_val in instance.params.items():
                    if isinstance(p_val, str) and p_val.strip().startswith("$"):
                        var_name = p_val.strip()[1:]
                        if var_name in self.params:
                            instance.params[p_key] = self.params[var_name]
                if hasattr(instance, "reset"):
                    instance.reset()
                
                # Tag ports for data bridging
                if b_type == "InputPort": instance.is_subsystem_input = True
                if b_type == "OutputPort": instance.is_subsystem_output = True
                
                self.execution_blocks.append(instance)
                self.execution_map[b_data["id"]] = instance

        # Restore Internal Connections
        for c_data in self.internal_connections_data:
            source = self.execution_map.get(c_data["from_block_id"])
            target = self.execution_map.get(c_data["to_block_id"])
            if source and target:
                out_p = source.outputs.get(c_data["from_port"])
                in_p = target.inputs.get(c_data["to_port"])
                if out_p and in_p:
                    in_p.connected_port = out_p

    def compute(self, t, dt):
        if not self.execution_blocks: return

        # 1. Bridge External Inputs -> Internal InputPorts
        for b in self.execution_blocks:
            if getattr(b, 'is_subsystem_input', False):
                p_name = b.params.get("PortName")
                if p_name in self.inputs:
                    b.outputs["out"].value = self.inputs[p_name].value

        # 2. Run Internal Blocks
        for b in self.execution_blocks:
            # Transfer data internally
            for name, port in b.inputs.items():
                if port.connected_port:
                    port.value = port.connected_port.value
            b.compute(t, dt)
            if hasattr(b, 'update_state'):
                b.update_state(t, dt)

        # 3. Bridge Internal OutputPorts -> External Outputs
        for b in self.execution_blocks:
            if getattr(b, 'is_subsystem_output', False):
                p_name = b.params.get("PortName")
                if p_name in self.outputs:
                        self.outputs[p_name].value = b.inputs["in"].value

    def get_editor_dialog(self, parent=None):
        """Custom dialog to edit SubGraph parameters and variables."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                       QTableWidget, QTableWidgetItem, 
                                       QPushButton, QLabel, QLineEdit, 
                                       QDialogButtonBox, QHeaderView, QWidget, QMessageBox)
        from PySide6.QtCore import Qt

        dialog = QDialog(parent)
        dialog.setWindowTitle("SubGraph Interface Editor")
        dialog.resize(500, 400)
        
        layout = QVBoxLayout(dialog)

        # --- Top Section: Name ---
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Block Name:"))
        name_edit = QLineEdit(self.params.get("BlockName", "MySubGraph"))
        name_layout.addWidget(name_edit)
        layout.addLayout(name_layout)
        
        # --- Middle Section: Parameters Table ---
        layout.addWidget(QLabel("<b>Custom Variables:</b>"))
        layout.addWidget(QLabel("Define variables here. Use them inside as <i>$VariableName</i>."))
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Name", "Value"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)
        
        def add_row(key="", val=""):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(key)))
            table.setItem(row, 1, QTableWidgetItem(str(val)))
            
        # Populate existing (excluding BlockName)
        for k, v in self.params.items():
            if k == "BlockName": continue
            add_row(k, v)
        
        # If empty, add a placeholder example? No, cleaner to leave empty.
        
        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Variable")
        btn_remove = QPushButton("Remove Selected")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)
        
        def on_add():
            add_row("NewVar", "0.0")
            
        def on_remove():
            rows = sorted(set(index.row() for index in table.selectedIndexes()), reverse=True)
            for r in rows:
                table.removeRow(r)
                
        btn_add.clicked.connect(on_add)
        btn_remove.clicked.connect(on_remove)
        
        # --- Dialog Buttons ---
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        original_accept = dialog.accept
        
        def save_and_accept():
            # 1. Validate
            new_params = {}
            new_params["BlockName"] = name_edit.text().strip()
            
            for i in range(table.rowCount()):
                key_item = table.item(i, 0)
                val_item = table.item(i, 1)
                
                if key_item and val_item:
                    key = key_item.text().strip()
                    val_str = val_item.text().strip()
                    
                    if not key:
                        continue
                        
                    if key == "BlockName":
                        QMessageBox.warning(dialog, "Invalid Name", "'BlockName' is reserved.")
                        return

                    # Try float conversion
                    try:
                        val = float(val_str)
                    except ValueError:
                        val = val_str
                        
                    new_params[key] = val
            
            # 2. Update self.params
            self.params = new_params
            
            # 3. Trigger updates
            if hasattr(self, "_update_label"):
                self._update_label()
                
            original_accept()

        dialog.accept = save_and_accept
        
        return dialog