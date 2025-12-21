from collections import deque
from ..models import BlockModel
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QFormLayout, 
                               QSpinBox, QDoubleSpinBox, QDialogButtonBox)

class DelayDialog(QDialog):
    """
    Dialog to configure the Delay block.
    Allows setting the number of steps (n) and the initial output value.
    """
    def __init__(self, params, parent=None):
        super().__init__(parent)
        self.params = params
        self.setWindowTitle("Delay Configuration")
        self.resize(300, 150)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        # 1. Delay Steps (N)
        self.spin_n = QSpinBox()
        self.spin_n.setRange(0, 99999) # Allow large buffers
        self.spin_n.setValue(int(self.params.get("DelaySteps", 1)))
        self.spin_n.setSuffix(" steps")
        form.addRow("Delay (n):", self.spin_n)

        # 2. Initial Value
        self.spin_init = QDoubleSpinBox()
        self.spin_init.setRange(-999999.0, 999999.0)
        self.spin_init.setDecimals(4)
        self.spin_init.setValue(float(self.params.get("InitialValue", 0.0)))
        form.addRow("Initial Value:", self.spin_init)

        layout.addLayout(form)

        # Buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def accept(self):
        """Save values back to params."""
        self.params["DelaySteps"] = self.spin_n.value()
        self.params["InitialValue"] = self.spin_init.value()
        super().accept()


class Delay(BlockModel):
    """
    Discrete Delay Block (z^-n).
    Delays the input signal by n simulation steps.
    """
    
    BLOCK_INFO = {
        "description": "Delays the signal by N steps (z^-n)",
        "parameters": "DelaySteps (int), InitialValue (float)",
        "formula": "y[k] = u[k-n]",
        "usage": "Use to create echo effects, digital filters, or feedback loops.",
        "category": "Signal"
    }
    
    def __init__(self):
        super().__init__("Delay")
        self.add_input("in")
        self.add_output("out")
        
        # Default parameters
        self.add_param("DelaySteps", 1)
        self.add_param("InitialValue", 0.0)
        
        # State: A ring buffer
        self.buffer = np.zeros(1, dtype=np.float64)
        self.ptr = 0
        self._cached_n = 1
        self._cached_init = 0.0
        self._cache_params()

    def _cache_params(self):
        try:
            old_n = self._cached_n
            self._cached_n = max(0, int(self.params.get("DelaySteps", 1)))
            self._cached_init = float(self.params.get("InitialValue", 0.0))
            
            # Re-allocate buffer if size changed
            if self._cached_n != old_n:
                self.buffer = np.full(self._cached_n + 1, self._cached_init, dtype=np.float64)
                self.ptr = 0
        except:
            pass

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def reset(self):
        """Resets the internal buffer."""
        self.buffer.fill(self._cached_init)
        self.ptr = 0

    def compute(self, t, dt, context=None):
        n = self._cached_n
        
        # Handle zero delay case (Pass-through)
        if n <= 0:
            self.outputs["out"].value = self.inputs["in"].value
            return

        # 1. Output the current value at ptr
        self.outputs["out"].value = float(self.buffer[self.ptr])

        # 2. Store new input at ptr
        self.buffer[self.ptr] = self.inputs["in"].value

        # 3. Advance pointer
        self.ptr = (self.ptr + 1) % (n + 1)

    def get_editor_dialog(self, parent=None):
        """Return the custom configuration dialog."""
        return DelayDialog(self.params, parent=parent)