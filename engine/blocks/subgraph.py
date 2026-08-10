from ..models import BlockModel
from ._feedthrough_utils import feedthrough_pairs
from typing import Dict, Any, List

class SubGraph(BlockModel):
    """
    A container block that holds an internal graph, executed synchronously
    (inline, as part of the parent diagram's own step) each time the parent
    calls compute().
    """

    BLOCK_INFO = {
        "description": "Container block with custom interface/variables",
        "parameters": "BlockName",
        "formula": "Executes internal diagram with variable substitution ($VarName)",
        "usage": "Double-click to enter. Ctrl+Double-click to edit variables.",
        "category": "Structure"
    }

    def __init__(self):
        super().__init__("SubGraph")
        self.is_container = True

        # Internal structure data
        self.internal_blocks_data = []
        self.internal_connections_data = []
        self.execution_blocks = []
        self.execution_map = {}

        # Parameters
        self.add_param("BlockName", "MySubGraph")
        self.add_param("MaskIconPath", "")  # Optional custom icon; drawn by UIBlock.paint()

        self._feedthrough_cache_key = None
        self._feedthrough_cache = {}

        self._update_label()

    def _refresh_feedthrough_cache(self):
        key = (str(self.internal_blocks_data), str(self.internal_connections_data))
        if key != self._feedthrough_cache_key:
            self._feedthrough_cache = feedthrough_pairs(
                self.internal_blocks_data, self.internal_connections_data
            )
            self._feedthrough_cache_key = key
        return self._feedthrough_cache

    def feedthrough_pairs(self):
        """Precise per-(input,output)-pair feedthrough (see
        _feedthrough_utils.py): only the specific external input/output
        pairs with a feedthrough-only internal path are reported, instead
        of an all-or-nothing block-wide flag. A single unrelated
        feedthrough output (e.g. a diagnostic tap straight off a
        controller, unused anywhere) used to make EVERY input look coupled
        to EVERY output under the default all-or-nothing has_direct_feedthrough
        boolean, which caused real false-positive algebraic-loop errors.
        """
        return self._refresh_feedthrough_cache()

    @property
    def has_direct_feedthrough(self):
        """Whether ANY external output could depend on ANY external input
        within the same step. Kept for callers checking the coarse flag --
        True only if at least one internal InputPort has a feedthrough-only
        path to an internal OutputPort. A static, unconditional True here
        was a real bug: it flagged the common case of a feedback loop
        closed through a subsystem's own internal dynamics (an Integrator,
        Delay, or strictly-proper TransferFunction/StateSpace one level
        down) as an unresolvable algebraic loop, even though the loop was
        actually well broken. topological_sort itself uses the more
        precise feedthrough_pairs() above, not this coarse flag.
        """
        return any(self._refresh_feedthrough_cache().values())

    def _update_label(self):
        """Formats the name to show Type on top, Name below."""
        user_name = self.params.get("BlockName", "MySubGraph")
        self.name = f"SubGraph\n({user_name})"

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._update_label()

    # --- Port Management ---
    def sync_ports_from_data(self):
        """Reads internal_blocks_data to determine external inputs/outputs."""
        self.inputs.clear()
        self.outputs.clear()

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
        self.sync_ports_from_data()

    # --- Execution Logic ---

    def reset(self):
        """Prepare internal blocks for a fresh run."""
        self._instantiate_internal_blocks()

    def _instantiate_internal_blocks(self):
        from . import BLOCK_REGISTRY
        self.execution_blocks = []
        self.execution_map = {}

        # 1. Ensure Variable Defaults
        for b_data in self.internal_blocks_data:
            for p_val in b_data.get("params", {}).values():
                if isinstance(p_val, str) and p_val.strip().startswith("$"):
                    var_name = p_val.strip()[1:]
                    if var_name and var_name not in self.params:
                        self.params[var_name] = 0.0

        # 2. Instantiate
        for b_data in self.internal_blocks_data:
            b_type = b_data["type"]
            if b_type in BLOCK_REGISTRY:
                instance = BLOCK_REGISTRY[b_type]()
                instance.params = b_data["params"].copy()

                # Variable Substitution
                substituted = False
                for p_key, p_val in instance.params.items():
                    if isinstance(p_val, str) and p_val.strip().startswith("$"):
                        var_name = p_val.strip()[1:]
                        if var_name in self.params:
                            instance.params[p_key] = self.params[var_name]
                            substituted = True

                if substituted:
                    # In-place dict mutation above doesn't fire the
                    # __setattr__ hook several blocks use to refresh cached
                    # params (e.g. Gain._cached_gain). Reassign to retrigger
                    # it now that substituted values are in place.
                    instance.params = instance.params

                if hasattr(instance, "reset"):
                    instance.reset()

                # Tags
                if b_type == "InputPort": instance.is_subsystem_input = True
                if b_type == "OutputPort": instance.is_subsystem_output = True

                self.execution_blocks.append(instance)
                self.execution_map[b_data["id"]] = instance

        # 3. Connections
        for c_data in self.internal_connections_data:
            source = self.execution_map.get(c_data["from_block_id"])
            target = self.execution_map.get(c_data["to_block_id"])
            if source and target:
                out_p = source.outputs.get(c_data["from_port"])
                in_p = target.inputs.get(c_data["to_port"])
                if out_p and in_p:
                    in_p.connected_port = out_p

    def compute(self, t, dt, context=None):
        if not self.execution_blocks:
            return

        # 1. Bridge External Inputs -> Internal InputPorts
        for b in self.execution_blocks:
            if getattr(b, 'is_subsystem_input', False):
                p_name = b.params.get("PortName")
                if p_name in self.inputs:
                    b.outputs["out"].value = self.inputs[p_name].value

        # 2. Run Internal Blocks
        # Cache stateful blocks to avoid hasattr() in loop
        stateful = getattr(self, "_stateful_inner", None)
        if stateful is None:
            stateful = [b for b in self.execution_blocks if hasattr(b, "update_state")]
            self._stateful_inner = stateful

        # Compute
        for b in self.execution_blocks:
            # Transfer data internally
            for port in b.inputs.values():
                if port.connected_port:
                    port.value = port.connected_port.value
            b.compute(t, dt, context=context)

        # Update State
        for b in stateful:
            b.update_state(t, dt, context=context)

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
                                       QDialogButtonBox, QHeaderView, QMessageBox,
                                       QFileDialog)

        dialog = QDialog(parent)
        dialog.setWindowTitle("SubGraph Interface Editor")
        dialog.resize(500, 500)

        layout = QVBoxLayout(dialog)

        # --- Section 1: General Settings ---
        form_layout = QVBoxLayout()

        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Block Name:"))
        name_edit = QLineEdit(self.params.get("BlockName", "MySubGraph"))
        name_layout.addWidget(name_edit)
        form_layout.addLayout(name_layout)

        # Mask Icon (optional custom icon shown on the block instead of the
        # generic title text -- see UIBlock.paint()'s MaskIconPath hook)
        icon_layout = QHBoxLayout()
        icon_layout.addWidget(QLabel("Mask Icon:"))
        icon_edit = QLineEdit(self.params.get("MaskIconPath", ""))
        icon_edit.setReadOnly(True)
        icon_layout.addWidget(icon_edit)
        btn_choose_icon = QPushButton("Choose...")
        btn_clear_icon = QPushButton("Clear")
        icon_layout.addWidget(btn_choose_icon)
        icon_layout.addWidget(btn_clear_icon)
        form_layout.addLayout(icon_layout)

        def on_choose_icon():
            path, _ = QFileDialog.getOpenFileName(
                dialog, "Choose Mask Icon", "",
                "Images (*.png *.jpg *.jpeg *.svg *.bmp)"
            )
            if path:
                icon_edit.setText(path)

        def on_clear_icon():
            icon_edit.setText("")

        btn_choose_icon.clicked.connect(on_choose_icon)
        btn_clear_icon.clicked.connect(on_clear_icon)

        layout.addLayout(form_layout)

        # --- Section 2: Variables ---
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

        # Populate
        reserved = ["BlockName", "MaskIconPath"]
        for k, v in self.params.items():
            if k in reserved: continue
            add_row(k, v)

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
            new_params = {}
            new_params["BlockName"] = name_edit.text().strip()
            new_params["MaskIconPath"] = icon_edit.text().strip()

            for i in range(table.rowCount()):
                key_item = table.item(i, 0)
                val_item = table.item(i, 1)

                if key_item and val_item:
                    key = key_item.text().strip()
                    val_str = val_item.text().strip()

                    if not key: continue
                    if key in reserved:
                        QMessageBox.warning(dialog, "Invalid Name", f"'{key}' is reserved.")
                        return

                    # Try float conversion
                    try:
                        val = float(val_str)
                    except ValueError:
                        val = val_str
                    new_params[key] = val

            self.params = new_params
            if hasattr(self, "_update_label"):
                self._update_label()

            original_accept()

        dialog.accept = save_and_accept

        return dialog
