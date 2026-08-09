"""BusSelector block: pick channels out of a bus signal by name (or 1-based index)."""
import numpy as np
from ..models import BlockModel
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPlainTextEdit, QDialogButtonBox


class BusSelectorDialog(QDialog):
    """Edit the ordered list of channel selectors (names, or 1-based indices
    as a fallback when the upstream block isn't a BusCreator)."""

    def __init__(self, block, parent=None):
        super().__init__(parent)
        self.block = block
        self.setWindowTitle("Configure Bus Selector")
        self.resize(360, 300)

        layout = QVBoxLayout(self)

        upstream_names = block.get_upstream_signal_names()
        if upstream_names:
            hint = "Upstream bus channels: " + ", ".join(upstream_names)
        else:
            hint = ("Upstream channel names unavailable (not wired to a Bus Creator) -- "
                    "enter 1-based channel indices instead.")
        info = QLabel(hint)
        info.setWordWrap(True)
        layout.addWidget(info)

        layout.addWidget(QLabel("Channels to output (one per line, name or 1-based index):"))
        self.text = QPlainTextEdit()
        self.text.setPlainText("\n".join(str(s) for s in block.params.get("SelectedSignals", ["1"])))
        layout.addWidget(self.text)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

        original_accept = self.accept

        def accept_with_apply():
            selections = [line.strip() for line in self.text.toPlainText().splitlines() if line.strip()]
            if not selections:
                selections = ["1"]
            self.block.params["SelectedSignals"] = selections
            self.block.refresh_io_ports()
            self.block.needs_port_refresh = True
            original_accept()

        self.accept = accept_with_apply


class BusSelector(BlockModel):
    """Picks named (or 1-based indexed) channels out of a bus signal.
    Pair with BusCreator for name-based selection; an unresolvable name or
    an out-of-range index outputs 0.0 rather than raising, consistent with
    this codebase's "no port type-checking, don't crash" philosophy.
    """

    BLOCK_INFO = {
        "description": "Picks named (or indexed) channels out of a bus signal",
        "parameters": "SelectedSignals (list of channel names or 1-based indices, in output order)",
        "formula": "out_i = bus[index_of(SelectedSignals[i])]",
        "usage": "Pair with Bus Creator to unpack specific channels of a named bus by name.",
        "category": "Signal Routing"
    }

    def __init__(self):
        super().__init__("BusSelector")
        self.add_param("SelectedSignals", ["1"])
        self.add_input("in")
        self.needs_port_refresh = False
        self.refresh_io_ports()

    def get_upstream_signal_names(self):
        """Best-effort introspection of the connected BusCreator's channel
        names, for the dialog's convenience. Returns [] if not connected to
        one (e.g. connected to Mux, or nothing)."""
        src = self.inputs["in"].connected_port
        if src is not None and hasattr(src.owner, "params"):
            names = src.owner.params.get("SignalNames")
            if names:
                return list(names)
        return []

    def refresh_io_ports(self):
        selections = self.params.get("SelectedSignals") or ["1"]
        target = max(1, min(16, len(selections)))
        selections = list(selections[:target])
        self.params["SelectedSignals"] = selections

        current = len(self.outputs)
        if target > current:
            for i in range(current + 1, target + 1):
                self.add_output(f"out{i}")
        elif target < current:
            for i in range(target + 1, current + 1):
                name = f"out{i}"
                if name in self.outputs:
                    del self.outputs[name]

    def _resolve_index(self, selector, upstream_names, width):
        if upstream_names and selector in upstream_names:
            return upstream_names.index(selector)
        try:
            idx = int(selector) - 1
            if 0 <= idx < width:
                return idx
        except (TypeError, ValueError):
            pass
        return None

    def compute(self, t, dt, context=None):
        bus = np.asarray(self.inputs["in"].bus_value, dtype=float)
        upstream_names = self.get_upstream_signal_names()
        selections = self.params.get("SelectedSignals") or []
        for i, selector in enumerate(selections, start=1):
            idx = self._resolve_index(selector, upstream_names, bus.size)
            val = float(bus[idx]) if idx is not None else 0.0
            self.outputs[f"out{i}"].value = val

    def get_editor_dialog(self, parent=None):
        return BusSelectorDialog(self, parent)
