from ..models import BlockModel


class Scope(BlockModel):
    def __init__(self):
        super().__init__("Scope")
        self.add_input("in")
        self.history_t = []
        self.history_y = []

    def compute(self, t, dt):
        val = self.inputs["in"].value
        self.history_t.append(t)
        self.history_y.append(val)

    def reset(self):
        self.history_t = []
        self.history_y = []

    def get_editor_dialog(self, parent=None):
        """Return a dialog for viewing the scope plot."""
        from PySide6.QtWidgets import QDialog, QVBoxLayout
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
        from matplotlib.figure import Figure

        dialog = QDialog(parent)
        dialog.setWindowTitle("Scope Result")
        layout = QVBoxLayout(dialog)

        fig = Figure(figsize=(5, 4), dpi=100)
        canvas = FigureCanvasQTAgg(fig)
        ax = fig.add_subplot(111)

        if self.history_t:
            ax.plot(self.history_t, self.history_y)
            ax.grid(True)
            ax.set_xlabel("Time (s)")
            ax.set_ylabel("Amplitude")
        else:
            ax.text(0.5, 0.5, "No Data. Run Simulation.", ha='center')

        layout.addWidget(canvas)
        return dialog
