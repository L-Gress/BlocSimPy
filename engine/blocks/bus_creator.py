"""BusCreator block: combine N named scalar inputs into one named bus signal."""
import numpy as np
from ..models import BlockModel
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox


class BusCreatorDialog(QDialog):
    """Edit the ordered list of channel names; port count follows the list length."""

    def __init__(self, block, parent=None):
        super().__init__(parent)
        self.block = block
        self.setWindowTitle("Configure Bus Creator")
        self.resize(320, 260)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Signal names (one per line, in bus order):"))
        self.text = QPlainTextEdit()
        self.text.setPlainText("\n".join(block.params.get("SignalNames", ["Signal1", "Signal2"])))
        layout.addWidget(self.text)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        original_accept = self.accept

        def accept_with_apply():
            names = [line.strip() for line in self.text.toPlainText().splitlines() if line.strip()]
            if not names:
                names = ["Signal1"]
            self.block.params["SignalNames"] = names
            self.block.refresh_io_ports()
            self.block.needs_port_refresh = True
            original_accept()

        self.accept = accept_with_apply


class BusCreator(BlockModel):
    """Like Mux, but each input port has an associated channel name so
    BusSelector can pick channels by name instead of position.
    """

    BLOCK_INFO = {
        "description": "Combines N named scalar signals into one named bus signal",
        "parameters": "SignalNames (list of channel names, in bus order)",
        "formula": "out = [in(SignalNames[0]), in(SignalNames[1]), ...]",
        "usage": "Like Mux, but pair with Bus Selector to pick channels back out by name.",
        "category": "Signal Routing"
    }

    def __init__(self):
        super().__init__("BusCreator")
        self.add_param("SignalNames", ["Signal1", "Signal2"])
        self.add_output("out")
        self.needs_port_refresh = False
        self.refresh_io_ports()

    def refresh_io_ports(self):
        names = self.params.get("SignalNames") or ["Signal1"]
        target = max(1, min(16, len(names)))
        names = list(names[:target])
        self.params["SignalNames"] = names

        current = len(self.inputs)
        if target > current:
            for i in range(current + 1, target + 1):
                self.add_input(f"in{i}")
        elif target < current:
            for i in range(target + 1, current + 1):
                name = f"in{i}"
                if name in self.inputs:
                    del self.inputs[name]

    def compute(self, t, dt, context=None):
        n = len(self.inputs)
        values = [self.inputs[f"in{i}"].value for i in range(1, n + 1)]
        self.outputs["out"].bus_value = np.array(values, dtype=float)

    def get_editor_dialog(self, parent=None):
        return BusCreatorDialog(self, parent)
