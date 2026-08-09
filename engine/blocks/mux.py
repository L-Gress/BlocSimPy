"""Mux block: combine N scalar inputs into one bus (vector) output signal."""
import numpy as np
from ..models import BlockModel
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QSpinBox, QDialogButtonBox)


class MuxDialog(QDialog):
    """Configure the number of scalar inputs combined into the output bus."""

    def __init__(self, block, parent=None):
        super().__init__(parent)
        self.block = block
        self.setWindowTitle("Configure Mux")
        self.resize(280, 130)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Number of inputs:"))
        self.spin = QSpinBox()
        self.spin.setRange(2, 16)
        self.spin.setValue(int(block.params.get("NumInputs", 2)))
        row.addWidget(self.spin)
        layout.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        original_accept = self.accept

        def accept_with_apply():
            self.block.params["NumInputs"] = self.spin.value()
            self.block.refresh_io_ports()
            self.block.needs_port_refresh = True
            original_accept()

        self.accept = accept_with_apply


class Mux(BlockModel):
    """Combines N scalar inputs into a single bus (vector) output signal,
    read downstream via port.bus_value (see PortModel.bus_value in
    engine/models.py). Pair with Demux to split a bus back into scalars.
    """

    BLOCK_INFO = {
        "description": "Combines N scalar signals into one bus (vector) signal",
        "parameters": "NumInputs (2-16)",
        "formula": "out = [in1, in2, ..., inN]",
        "usage": "Group related signals to route together; pair with Demux to split them back out.",
        "category": "Signal Routing"
    }

    def __init__(self):
        super().__init__("Mux")
        self.add_param("NumInputs", 2)
        self.add_output("out")
        self.needs_port_refresh = False
        self.refresh_io_ports()

    def refresh_io_ports(self):
        target = max(2, min(16, int(self.params.get("NumInputs", 2))))
        current = len(self.inputs)

        if target > current:
            for i in range(current + 1, target + 1):
                self.add_input(f"in{i}")
        elif target < current:
            for i in range(target + 1, current + 1):
                name = f"in{i}"
                if name in self.inputs:
                    del self.inputs[name]

        self.params["NumInputs"] = target

    def compute(self, t, dt, context=None):
        n = len(self.inputs)
        values = [self.inputs[f"in{i}"].value for i in range(1, n + 1)]
        self.outputs["out"].bus_value = np.array(values, dtype=float)

    def get_editor_dialog(self, parent=None):
        return MuxDialog(self, parent)
