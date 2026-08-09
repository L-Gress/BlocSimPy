"""Demux block: split a bus (vector) input signal into N scalar outputs."""
import numpy as np
from ..models import BlockModel
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QSpinBox, QDialogButtonBox)


class DemuxDialog(QDialog):
    """Configure the number of scalar outputs split out of the input bus."""

    def __init__(self, block, parent=None):
        super().__init__(parent)
        self.block = block
        self.setWindowTitle("Configure Demux")
        self.resize(280, 130)

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        row.addWidget(QLabel("Number of outputs:"))
        self.spin = QSpinBox()
        self.spin.setRange(2, 16)
        self.spin.setValue(int(block.params.get("NumOutputs", 2)))
        row.addWidget(self.spin)
        layout.addLayout(row)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        original_accept = self.accept

        def accept_with_apply():
            self.block.params["NumOutputs"] = self.spin.value()
            self.block.refresh_io_ports()
            self.block.needs_port_refresh = True
            original_accept()

        self.accept = accept_with_apply


class Demux(BlockModel):
    """Splits one bus (vector) input signal into N scalar outputs. Width
    mismatch is tolerated (missing channels output 0.0), consistent with
    this codebase's "no port type-checking, don't crash" philosophy.
    """

    BLOCK_INFO = {
        "description": "Splits one bus (vector) signal into N scalar signals",
        "parameters": "NumOutputs (2-16)",
        "formula": "out_i = in[i]",
        "usage": "Pair with Mux to unpack a grouped signal back into scalars.",
        "category": "Signal Routing"
    }

    def __init__(self):
        super().__init__("Demux")
        self.add_param("NumOutputs", 2)
        self.add_input("in")
        self.needs_port_refresh = False
        self.refresh_io_ports()

    def refresh_io_ports(self):
        target = max(2, min(16, int(self.params.get("NumOutputs", 2))))
        current = len(self.outputs)

        if target > current:
            for i in range(current + 1, target + 1):
                self.add_output(f"out{i}")
        elif target < current:
            for i in range(target + 1, current + 1):
                name = f"out{i}"
                if name in self.outputs:
                    del self.outputs[name]

        self.params["NumOutputs"] = target

    def compute(self, t, dt, context=None):
        bus = np.asarray(self.inputs["in"].bus_value, dtype=float)
        n = len(self.outputs)
        for i in range(1, n + 1):
            val = float(bus[i - 1]) if i - 1 < bus.size else 0.0
            self.outputs[f"out{i}"].value = val

    def get_editor_dialog(self, parent=None):
        return DemuxDialog(self, parent)
