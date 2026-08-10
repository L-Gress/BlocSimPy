import numpy as np
from ..models import BlockModel
from ._poly_utils import parse_coeffs, format_fraction_label

class TransferFunction(BlockModel):
    """Continuous-time Transfer Function (Laplace Domain).

    Represents H(s) = N(s) / D(s).
    The system is solved via State-Space conversion and numerical integration.
    """

    BLOCK_INFO = {
        "description": "Implements continuous transfer function H(s) = N(s)/D(s)",
        "parameters": "Numerator coefficients, Denominator coefficients (comma-separated)",
        "formula": "Uses discrete approximation with Tustin/bilinear transformation",
        "usage": "Model linear systems, filters, controllers (PID, lead-lag, etc.)",
        "category": "Signal"
    }

    def __init__(self):
        super().__init__("TransferFunction")
        self.add_input("in")
        self.add_output("out")
        
        # Default: 1 / (s + 1)
        self.add_param("Numerator", [1.0])
        self.add_param("Denominator", [1.0, 1.0])

        # Internal state vector (integrators)
        self.states = [] 
        
        self._cache_key = None
        self._A_row = []  
        self._C = []      
        self._D = 0.0     
        
        # --- MODIFICATION: Update label on init ---
        self._update_label()

    def _update_label(self):
        """Updates block name to a 3-line ASCII fraction."""
        try:
            num = parse_coeffs(self.params.get("Numerator", [1.0]))
            den = parse_coeffs(self.params.get("Denominator", [1.0, 1.0]))
            self.name = format_fraction_label(num, den, variable="s")
        except:
            self.name = "TransferFunction"

    def _update_matrices(self):
        # ... (Existing Logic Unchanged) ...
        num_raw = parse_coeffs(self.params.get("Numerator", [1.0]))
        den_raw = parse_coeffs(self.params.get("Denominator", [1.0, 1.0]))

        if not den_raw: den_raw = [1.0]
        a0 = den_raw[0]
        if a0 == 0: a0 = 1.0 
        
        den = [d / a0 for d in den_raw]
        num = [n / a0 for n in num_raw]

        n = len(den) - 1 
        if len(num) < len(den):
            num = [0.0] * (len(den) - len(num)) + num
        
        self._D = num[0]
        self._C = []
        for i in range(1, len(den)):
            self._C.append(num[i] - den[i] * self._D)
            
        self._A_row = [-den[i] for i in range(len(den)-1, 0, -1)]

        target_order = n
        if len(self.states) != target_order:
            self.states = [0.0] * target_order

    def _refresh_matrices_if_needed(self):
        current_params = (str(self.params["Numerator"]), str(self.params["Denominator"]))
        if current_params != self._cache_key:
            self._update_matrices()
            self._cache_key = current_params

    @property
    def has_direct_feedthrough(self):
        """Whether this step's output depends on this step's own input,
        i.e. whether D != 0 for the currently configured coefficients.
        A strictly proper transfer function (D == 0 -- e.g. this block's
        own default, 1/(s+1)) has NO direct feedthrough: its output only
        depends on internal state, exactly like Integrator/Delay, so a
        feedback loop closed through one is well-defined and must NOT be
        flagged as an algebraic loop. Computed live (not a fixed class
        attribute) so it tracks whatever coefficients are configured --
        a static True here was a real bug: it flagged the extremely common
        case of closing a loop through a strictly-proper TF as an
        unresolvable algebraic loop.
        """
        self._refresh_matrices_if_needed()
        return self._D != 0

    def _derivatives_for(self, u, states):
        """Pure: d(states)/dt at the given state vector, given input u."""
        n = len(states)
        if n == 0:
            return []
        derivatives = [0.0] * n
        for i in range(n - 1):
            derivatives[i] = states[i + 1]
        last_dot = u
        for i in range(n):
            last_dot += self._A_row[i] * states[i]
        derivatives[n - 1] = last_dot
        return derivatives

    def compute(self, t, dt, context=None):
        # Output only. State integration happens in update_state() (Euler)
        # or is driven externally by a Solver (e.g. RK4) via get_derivative()/
        # get_state()/set_state() -- see those methods below. This mirrors
        # the existing Integrator pattern: compute() reads current state,
        # a later pass advances it.
        if dt <= 0: return

        self._refresh_matrices_if_needed()

        u = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        n = len(self.states)

        if n == 0:
            self.outputs["out"].value = self._D * u
            return

        y = self._D * u
        for i in range(n):
            y += self._C[i] * self.states[n - 1 - i]

        self.outputs["out"].value = y

    def update_state(self, t, dt, context=None):
        # Euler integration (default path; RK4Solver bypasses this and uses
        # get_derivative()/get_state()/set_state() directly instead).
        if dt <= 0: return
        n = len(self.states)
        if n == 0: return

        u = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        derivatives = self._derivatives_for(u, self.states)
        for i in range(n):
            self.states[i] += derivatives[i] * dt

    def get_derivative(self, t, dt):
        self._refresh_matrices_if_needed()
        n = len(self.states)
        if n == 0:
            return np.array([])
        u = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        return np.array(self._derivatives_for(u, self.states))

    def get_state(self):
        return np.array(self.states, dtype=float)

    def set_state(self, vec):
        self.states = [float(v) for v in vec]

    def reset(self):
        self.states = [0.0] * len(self.states)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QLabel

        dialog = QDialog(parent)
        # Since self.name is now multi-line, we assume the window title can handle it or we strip it
        dialog.setWindowTitle("Edit Transfer Function")
        layout = QFormLayout(dialog)

        info = QLabel(
            "Continuous-time Transfer Function.\n"
            "Format: Coefficients of 's' in descending order."
        )
        info.setWordWrap(True)
        layout.addRow(info)

        num_edit = QLineEdit(", ".join(str(x) for x in self.params.get("Numerator", [1.0])))
        den_edit = QLineEdit(", ".join(str(x) for x in self.params.get("Denominator", [1.0])))

        layout.addRow("Numerator (b):", num_edit)
        layout.addRow("Denominator (a):", den_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            self.params["Numerator"] = [float(x.strip()) for x in num_edit.text().split(',') if x.strip()]
            self.params["Denominator"] = [float(x.strip()) for x in den_edit.text().split(',') if x.strip()]
            self._cache_key = None 
            self.reset()
            # --- MODIFICATION: Update visual label on save ---
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog