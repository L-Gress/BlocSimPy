"""Embeddable simulation-results page: every Scope's recorded signal from
one simulation run, shown together as a central-area tab (see
MainWindow.open_simulation_tab()) rather than a modal dialog -- so
multiple runs' results can stay open and be compared side by side instead
of only the most recent being reachable.

Reuses SimulationEngine.run()'s existing result.scope_data (already
aggregated by the engine -- see engine/simulation/engine.py) rather than
re-deriving it, and the same SignalPlotWidget ScopeDialog uses.
"""
import csv
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel,
                               QPushButton, QFileDialog, QMessageBox)
from .signal_plot_widget import SignalPlotWidget


class SimulationResultWidget(QWidget):
    def __init__(self, result, title="Simulation", parent=None):
        super().__init__(parent)

        self._series = {
            name: (entry.get("time"), entry.get("data"))
            for name, entry in (result.scope_data.items() if result else [])
        }

        layout = QVBoxLayout(self)

        header = QLabel(title)
        header_font = header.font()
        header_font.setBold(True)
        header_font.setPointSize(12)
        header.setFont(header_font)
        layout.addWidget(header)

        info = QLabel(
            "Shows each Scope's primary (first) input channel from this run. "
            "Double-click an individual Scope block to see all of its channels."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(info)

        self.plot = SignalPlotWidget(title=title, parent=self)
        self.plot.set_series(self._series)
        layout.addWidget(self.plot)

        btn_layout = QHBoxLayout()
        export_btn = QPushButton("⬇ Export CSV")
        export_btn.clicked.connect(self._export_csv)
        btn_layout.addWidget(export_btn)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

    def _export_csv(self):
        """Export every Scope's series shown here into one CSV: a Time
        column plus one data column per Scope. All series come from the
        same simulation run, so they share one time base -- the shortest
        one is used if lengths ever differ, to stay in bounds."""
        if not self._series:
            self._status("This run has no Scope data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Simulation Results", "", "CSV Files (*.csv)")
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
            self._status(f"Exported to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _status(self, message):
        """Routine, non-blocking confirmation shown in the main window's
        status bar instead of an interrupting QMessageBox.information() --
        see MainWindow.show_status(). Safe now that this is an embedded
        tab rather than a modal dialog (which would hide the status bar)."""
        main_window = self.window()
        if hasattr(main_window, "show_status"):
            main_window.show_status(message)
