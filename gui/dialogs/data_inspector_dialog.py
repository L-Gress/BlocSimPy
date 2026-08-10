"""Data Inspector: view every Scope's recorded signal from the last
simulation run in one place, without opening each Scope block individually.

Reuses SimulationEngine.run()'s existing result.scope_data (already
aggregated by the engine -- see engine/simulation/engine.py) rather than
re-deriving it, and the same SignalPlotWidget ScopeDialog uses.
"""
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QDialogButtonBox
from ..widgets import SignalPlotWidget


class DataInspectorDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Inspector")
        self.resize(1000, 650)

        layout = QVBoxLayout(self)

        info = QLabel(
            "Shows each Scope's primary (first) input channel from the last run. "
            "Double-click an individual Scope block to see all of its channels."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(info)

        series = {
            name: (entry.get("time"), entry.get("data"))
            for name, entry in (result.scope_data.items() if result else [])
        }
        self.plot = SignalPlotWidget(title="Data Inspector", parent=self)
        self.plot.set_series(series)
        layout.addWidget(self.plot)

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.accept)
        close_btn = btns.button(QDialogButtonBox.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        layout.addWidget(btns)
