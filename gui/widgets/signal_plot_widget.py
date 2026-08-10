"""Reusable multi-signal time-series plot with a Matplotlib zoom/pan
toolbar. Factored out of Scope's ScopeDialog (engine/blocks/scope.py) so
the Data Inspector (gui/dialogs/data_inspector_dialog.py) can reuse the
exact same plotting code instead of duplicating it -- ScopeDialog itself
was refactored to use this widget too.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

# Color palette for multiple signals (matches the original ScopeDialog's).
_COLORS = [
    '#2E86AB', '#A23B72', '#F18F01', '#C73E1D',
    '#6A994E', '#BC4B51', '#4A5899', '#8E3B46',
    '#118AB2', '#EF476F', '#06D6A0', '#FFD166'
]


class SignalPlotWidget(QWidget):
    """Plots one or more named time-series signals with a zoom/pan toolbar."""

    def __init__(self, title="Signal", parent=None):
        super().__init__(parent)
        self._title = title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(figsize=(12, 7), dpi=100)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._toolbar.setStyleSheet("QToolBar { spacing: 5px; padding: 5px; }")
        self._ax = self._fig.add_subplot(111)

        self._info_label = QLabel()
        self._info_label.setStyleSheet("font-weight: bold; color: #2E86AB; font-size: 10pt;")

        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        info_layout = QHBoxLayout()
        info_layout.addWidget(self._info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        self.set_series({})

    def set_series(self, series):
        """series: {label: (time_array, value_array)}. Replaces the current plot."""
        self._ax.clear()
        total_samples = 0
        max_duration = 0.0
        plotted = 0

        if series:
            for idx, (label, (time_array, value_array)) in enumerate(series.items()):
                if len(value_array) == 0:
                    continue
                color = _COLORS[idx % len(_COLORS)]
                self._ax.plot(time_array, value_array, label=label,
                              color=color, linewidth=2, alpha=0.85)
                plotted += 1
                total_samples = max(total_samples, len(time_array))
                if len(time_array) > 0:
                    max_duration = max(max_duration, time_array[-1])

        if plotted > 0:
            self._ax.grid(True, alpha=0.3, linestyle='--', linewidth=0.5)
            self._ax.set_xlabel("Time (s)", fontsize=12, fontweight='bold')
            self._ax.set_ylabel("Signal Value", fontsize=12, fontweight='bold')
            self._ax.set_title(self._title, fontsize=14, fontweight='bold', pad=15)
            if plotted > 1:
                self._ax.legend(loc='best', framealpha=0.95, edgecolor='gray',
                                fancybox=True, shadow=True)
            self._ax.margins(x=0.01, y=0.05)
            self._ax.spines['top'].set_visible(False)
            self._ax.spines['right'].set_visible(False)
            self._info_label.setText(
                f"📊 {plotted} signal(s) | {total_samples} samples | Duration: {max_duration:.3f}s"
            )
        else:
            self._ax.text(
                0.5, 0.5,
                "📊 No Data Available\n\nRun the simulation first to see results",
                ha='center', va='center', fontsize=14, color='#999',
                transform=self._ax.transAxes, weight='bold'
            )
            self._ax.set_xlim(0, 1)
            self._ax.set_ylim(0, 1)
            self._ax.axis('off')
            self._info_label.setText("📊 No data - run simulation to see results")

        self._fig.tight_layout()
        self._canvas.draw()
