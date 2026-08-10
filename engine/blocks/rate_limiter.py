from ..models import BlockModel

class RateLimiter(BlockModel):
    """Limits how fast the output can change per second (slew rate).

    Like Delay, this is a discrete state update done entirely inside
    compute() (state = previous output), not an ODE -- there's no
    get_derivative()/RK4 hook needed.
    """

    BLOCK_INFO = {
        "description": "Limits the rate of change of the signal (slew rate limiting)",
        "parameters": "Rising Slew Rate (units/s, >=0), Falling Slew Rate (units/s, <=0)",
        "formula": "out += clip(in - out_prev, FallingRate*dt, RisingRate*dt)",
        "usage": "Model actuator/physical rate limits, smooth step changes, prevent sudden jumps",
        "category": "Discontinuities"
    }

    def __init__(self):
        super().__init__("Rate Limiter")
        self.add_input("in")
        self.add_output("out")
        self.add_param("Rising Slew Rate", 1.0)
        self.add_param("Falling Slew Rate", -1.0)

        self.state = 0.0
        self.initialized = False
        self._cache_params()

    def _cache_params(self):
        try:
            self._rising = float(self.params.get("Rising Slew Rate", 1.0))
            self._falling = float(self.params.get("Falling Slew Rate", -1.0))
        except:
            self._rising = 1.0
            self._falling = -1.0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        val = float(self.inputs["in"].value)

        if not self.initialized:
            # No prior output to slew from -- pass the first sample through
            # unlimited, same convention as Integrator/Derivative's first-call handling.
            self.state = val
            self.initialized = True
        else:
            delta = val - self.state
            max_up = self._rising * dt
            max_down = self._falling * dt
            if delta > max_up:
                delta = max_up
            elif delta < max_down:
                delta = max_down
            self.state += delta

        self.outputs["out"].value = self.state

    def reset(self):
        self.initialized = False
        self.state = 0.0

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox
        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Rate Limiter")
        layout = QFormLayout(dialog)
        le_up = QLineEdit(str(self.params.get("Rising Slew Rate", 1.0)))
        le_down = QLineEdit(str(self.params.get("Falling Slew Rate", -1.0)))
        layout.addRow("Rising Slew Rate:", le_up)
        layout.addRow("Falling Slew Rate:", le_down)
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)
        def save():
            try:
                self.params["Rising Slew Rate"] = float(le_up.text())
                self.params["Falling Slew Rate"] = float(le_down.text())
                self._cache_params()
            except: pass
        dialog.accepted.connect(save)
        return dialog
