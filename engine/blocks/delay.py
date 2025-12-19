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
        
        # State: A queue to hold past values
        self.buffer = deque()

    def reset(self):
        """Resets the internal buffer."""
        self.buffer.clear()
        # We don't pre-fill here to save memory; we handle it in compute.

    def compute(self, t, dt):
        # 1. Parse parameters
        try:
            n = int(self.params["DelaySteps"])
            init_val = float(self.params["InitialValue"])
        except ValueError:
            n = 1
            init_val = 0.0

        # 2. Handle zero delay case (Pass-through)
        if n <= 0:
            self.outputs["out"].value = self.inputs["in"].value
            self.buffer.clear()
            return

        # 3. Add current input to buffer
        current_in = self.inputs["in"].value
        self.buffer.append(current_in)

        # 4. Determine output
        # If we haven't stored enough samples yet, output the Initial Value
        if len(self.buffer) > n:
            # Pop the oldest value (FIFO)
            self.outputs["out"].value = self.buffer.popleft()
        else:
            # Buffer filling up phase
            self.outputs["out"].value = init_val

    def get_editor_dialog(self, parent=None):
        """Return the custom configuration dialog."""
        return DelayDialog(self.params, parent=parent)