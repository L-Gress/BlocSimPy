from ..models import BlockModel
from ..variables import resolve_params, get_active_variables
from ._feedthrough_utils import feedthrough_pairs
from typing import Dict, Any, List

class SubGraph(BlockModel):
    """
    A container block that holds an internal graph, executed synchronously
    (inline, as part of the parent diagram's own step) each time the parent
    calls compute().
    """

    BLOCK_INFO = {
        "description": "Container block that holds its own internal diagram",
        "parameters": "BlockName",
        "formula": "Executes internal diagram; any internal block's param can be "
                    "bound to a global variable (see engine/variables.py) the same "
                    "way as any top-level block's",
        "usage": "Double-click to step inside and build its internal diagram.",
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

        # Global variable store to resolve any internal block's variable-
        # bound params against (see engine/variables.py) -- the SAME store
        # every top-level block resolves against (SimulationEngine.run()),
        # not a private per-SubGraph table: an internal block binds
        # directly to a real, globally-declared variable name, exactly
        # like a top-level block would. Read fresh every reset() (not
        # cached) so a variable's current value is picked up on each run.
        variables = get_active_variables()

        for b_data in self.internal_blocks_data:
            b_type = b_data["type"]
            if b_type in BLOCK_REGISTRY:
                instance = BLOCK_REGISTRY[b_type]()
                # resolve_params()'s `missing` half is deliberately ignored
                # here: SimulationEngine.check_diagram_detailed() already
                # walks internal_blocks_data recursively and blocks the run
                # on any undeclared reference before reset() is ever
                # reached, so nothing here should still be missing in
                # practice -- and if it is anyway, resolve_params() just
                # leaves that one param as the unresolved reference dict
                # rather than crashing.
                resolved_params, _missing = resolve_params(b_data.get("params", {}), variables)
                instance.params = dict(resolved_params)

                # A nested SubGraph's own internal_blocks_data/
                # internal_connections_data only live in the *design-time*
                # dict (b_data) -- a fresh BLOCK_REGISTRY["SubGraph"]()
                # instance starts with empty lists (see __init__), so they
                # must be copied over before reset() or the nested level
                # instantiates zero execution_blocks and silently computes
                # nothing (see engine/serialization/graph_serializer.py and
                # engine/blocks/_feedthrough_utils.py for the same pattern).
                if "internal_blocks_data" in b_data:
                    instance.internal_blocks_data = b_data.get("internal_blocks_data", [])
                    instance.internal_connections_data = b_data.get("internal_connections_data", [])
                    if hasattr(instance, "refresh_io_ports"):
                        instance.refresh_io_ports()

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
        """Dialog to edit this SubGraph's own settings (BlockName, optional
        Mask Icon). Binding an INTERNAL block's parameter to a global
        variable is done on that block's own parameter editor (the same
        "bind to variable" control any top-level block's editor has -- see
        gui/widgets/param_value_editor.py), after stepping inside this
        SubGraph -- not here. There's no separate per-SubGraph "Custom
        Variables" table anymore: an internal block binds directly to a
        real, globally-declared variable name, exactly like a top-level
        block would (see engine/variables.py)."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout,
                                       QPushButton, QLabel, QLineEdit,
                                       QDialogButtonBox, QFileDialog)

        dialog = QDialog(parent)
        dialog.setWindowTitle("SubGraph Settings")
        dialog.resize(420, 180)

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
        layout.addStretch()

        # --- Dialog Buttons ---
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        original_accept = dialog.accept

        def save_and_accept():
            new_params = dict(self.params)
            new_params["BlockName"] = name_edit.text().strip()
            new_params["MaskIconPath"] = icon_edit.text().strip()

            self.params = new_params
            if hasattr(self, "_update_label"):
                self._update_label()

            original_accept()

        dialog.accept = save_and_accept

        return dialog
