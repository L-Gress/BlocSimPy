"""Runs a configured SimulationEngine on a background QThread.

Keeps long simulations from freezing the UI: the engine's run() loop reports
progress and polls for cancellation every ~200th of the way through, both of
which this worker turns into Qt signals the main thread can react to.
"""
from PySide6.QtCore import QObject, Signal


class SimulationWorker(QObject):
    progress = Signal(float)
    finished = Signal(object)  # SimulationResult

    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        self._cancel_requested = False

    def cancel(self):
        self._cancel_requested = True

    def run(self):
        result = self.engine.run(
            progress_callback=self.progress.emit,
            should_cancel=lambda: self._cancel_requested,
        )
        self.finished.emit(result)
