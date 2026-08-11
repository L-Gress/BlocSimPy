"""Data Inspector: view every Scope's recorded signal from the last
simulation run in one place, without opening each Scope block individually.

Reuses SimulationEngine.run()'s existing result.scope_data (already
aggregated by the engine -- see engine/simulation/engine.py) rather than
re-deriving it, and the same SignalPlotWidget ScopeDialog uses.
"""
import csv
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                               QDialogButtonBox, QPushButton, QFileDialog, QMessageBox)
from ..widgets import SignalPlotWidget


class DataInspectorDialog(QDialog):
    def __init__(self, result, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Data Inspector")
        self.resize(1000, 650)

        self._series = {
            name: (entry.get("time"), entry.get("data"))
            for name, entry in (result.scope_data.items() if result else [])
        }

        layout = QVBoxLayout(self)

        info = QLabel(
            "Shows each Scope's primary (first) input channel from the last run. "
            "Double-click an individual Scope block to see all of its channels."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(info)

        self.plot = SignalPlotWidget(title="Data Inspector", parent=self)
        self.plot.set_series(self._series)
        layout.addWidget(self.plot)

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("⬇ Export CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()

        btns = QDialogButtonBox(QDialogButtonBox.Close)
        btns.rejected.connect(self.accept)
        close_btn = btns.button(QDialogButtonBox.Close)
        if close_btn:
            close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(btns)
        layout.addLayout(btn_layout)

    def _export_csv(self):
        """Export every Scope's series shown here into one CSV: a Time
        column plus one data column per Scope. All series come from the
        same simulation run, so they share one time base -- the shortest
        one is used if lengths ever differ, to stay in bounds."""
        if not self._series:
            QMessageBox.information(self, "No Data", "Run the simulation first to have data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Data Inspector", "", "CSV Files (*.csv)")
        if not file_path:
            return

        names = list(self._series.keys())
        time_arr = self._series[names[0]][0]
        row_count = min(len(self._series[name][0]) for name in names)

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Time"] + names)
                for i in range(row_count):
                    writer.writerow([time_arr[i]] + [self._series[name][1][i] for name in names])
            QMessageBox.information(self, "Export Complete", f"Saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))
