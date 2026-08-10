"""Reusable multi-signal time-series plot with a Matplotlib zoom/pan
toolbar. Factored out of Scope's ScopeDialog (engine/blocks/scope.py) so
the Data Inspector (gui/dialogs/data_inspector_dialog.py) can reuse the
exact same plotting code instead of duplicating it -- ScopeDialog itself
was refactored to use this widget too.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

# Color palette for multiple signals -- saturated system colors that still
# read clearly against the app's light canvas (config/theme.py).
_COLORS = [
    '#007AFF', '#FF9500', '#34C759', '#FF3B30',
    '#AF52DE', '#32ADE6', '#FFCC00', '#FF2D55',
    '#5856D6', '#00B4A6', '#A2845E', '#6E6E73'
]

_PLOT_BG = "#ffffff"
_AXES_BG = "#f9f9fb"
_FG = "#1d1d1f"
_GRID = "#8e8e93"
_SPINE = "#d1d1d6"


class SignalPlotWidget(QWidget):
    """Plots one or more named time-series signals with a zoom/pan toolbar."""

    def __init__(self, title="Signal", parent=None):
        super().__init__(parent)
        self._title = title

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._fig = Figure(figsize=(12, 7), dpi=100)
        self._fig.patch.set_facecolor(_PLOT_BG)
        self._canvas = FigureCanvasQTAgg(self._fig)
        self._toolbar = NavigationToolbar2QT(self._canvas, self)
        self._toolbar.setStyleSheet(
            f"QToolBar {{ background-color: {_PLOT_BG}; spacing: 5px; padding: 5px; border: none; }}"
        )
        self._ax = self._fig.add_subplot(111)

        self._info_label = QLabel()
        self._info_label.setStyleSheet(f"font-weight: 600; color: {_COLORS[0]}; font-size: 10pt;")

        layout.addWidget(self._toolbar)
        layout.addWidget(self._canvas)
        info_layout = QHBoxLayout()
        info_layout.addWidget(self._info_label)
        info_layout.addStretch()
        layout.addLayout(info_layout)

        self.set_series({})

    def _style_axes(self):
        """Re-applies dark theming to the axes -- needed after every
        ax.clear(), which resets matplotlib's own (light) defaults."""
        self._ax.set_facecolor(_AXES_BG)
        for spine in self._ax.spines.values():
            spine.set_color(_SPINE)
        self._ax.tick_params(colors=_FG)
        self._ax.xaxis.label.set_color(_FG)
        self._ax.yaxis.label.set_color(_FG)
        self._ax.title.set_color(_FG)

    def set_series(self, series):
        """series: {label: (time_array, value_array)}. Replaces the current plot."""
        self._ax.clear()
        self._style_axes()
        total_samples = 0
        max_duration = 0.0
        plotted = 0

        if series:
            for idx, (label, (time_array, value_array)) in enumerate(series.items()):
                if len(value_array) == 0:
                    continue
                color = _COLORS[idx % len(_COLORS)]
                self._ax.plot(time_array, value_array, label=label,
                              color=color, linewidth=2, alpha=0.9)
                plotted += 1
                total_samples = max(total_samples, len(time_array))
                if len(time_array) > 0:
                    max_duration = max(max_duration, time_array[-1])

        if plotted > 0:
            self._ax.grid(True, color=_GRID, alpha=0.2, linestyle='--', linewidth=0.5)
            self._ax.set_xlabel("Time (s)", fontsize=12, fontweight='bold')
            self._ax.set_ylabel("Signal Value", fontsize=12, fontweight='bold')
            self._ax.set_title(self._title, fontsize=14, fontweight='bold', pad=15)
            if plotted > 1:
                legend = self._ax.legend(loc='best', framealpha=0.9, edgecolor=_SPINE,
                                          fancybox=True, facecolor=_AXES_BG)
                for text in legend.get_texts():
                    text.set_color(_FG)
            self._ax.margins(x=0.01, y=0.05)
            self._ax.spines['top'].set_visible(False)
            self._ax.spines['right'].set_visible(False)
            self._info_label.setText(
                f"{plotted} signal(s) | {total_samples} samples | Duration: {max_duration:.3f}s"
            )
        else:
            self._ax.text(
                0.5, 0.5,
                "No Data Available\n\nRun the simulation first to see results",
                ha='center', va='center', fontsize=14, color=_GRID,
                transform=self._ax.transAxes, weight='bold'
            )
            self._ax.set_xlim(0, 1)
            self._ax.set_ylim(0, 1)
            self._ax.axis('off')
            self._info_label.setText("No data - run simulation to see results")

        self._fig.tight_layout()
        self._canvas.draw()
