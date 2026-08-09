from ..models import BlockModel

class Backlash(BlockModel):
    """Models mechanical backlash/play (e.g. loose gear teeth): the output
    only starts moving again once the input has reversed by more than the
    deadband width.

    Like Delay/RateLimiter, this is a discrete state update done entirely
    inside compute() (state = current output position); no ODE/RK4 hook,
    no custom compute_chunk() needed (default per-sample shim suffices).
    """

    BLOCK_INFO = {
        "description": "Models mechanical backlash/play (hysteresis dead-band around the output)",
        "parameters": "Deadband Width",
        "formula": "out unchanged while in stays within [out-W/2, out+W/2]; otherwise out = in -+ W/2",
        "usage": "Model gear backlash, loose linkages, or other mechanical play",
        "category": "Discontinuities"
    }

    def __init__(self):
        super().__init__("Backlash")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Deadband Width", 1.0)

        self.state = 0.0
        self.initialized = False
        self._cache_params()

    def _cache_params(self):
        try:
            self._width = max(0.0, float(self.params.get("Deadband Width", 1.0)))
        except:
            self._width = 1.0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        val = float(self.inputs["in"].value)
        half = self._width / 2.0

        if not self.initialized:
            # Start centered on the first input, same convention as
            # Integrator/Derivative's first-call handling.
            self.state = val
            self.initialized = True
        elif val > self.state + half:
            self.state = val - half
        elif val < self.state - half:
            self.state = val + half
        # else: input is still within the deadband around the current
        # output -- output doesn't move.

        self.outputs["out"].value = self.state

    def reset(self):
        self.initialized = False
        self.state = 0.0

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Backlash")
        layout = QFormLayout(dialog)
        le_width = QLineEdit(str(self.params.get("Deadband Width", 1.0)))
        layout.addRow("Deadband Width:", le_width)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        def save():
            try:
                self.params["Deadband Width"] = float(le_width.text())
                self._cache_params()
            except: pass
        dialog.accepted.connect(save)
        return dialog
