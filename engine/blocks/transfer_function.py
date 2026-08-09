import numpy as np
from ..models import BlockModel

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

    # The D term (direct feedthrough) means this step's output can depend on
    # this step's input even when D == 0 for the currently configured
    # coefficients, so this stays conservative (True) rather than being
    # derived from the live D value.
    has_direct_feedthrough = True

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

    def _parse_coeffs(self, val):
        if isinstance(val, (list, tuple)):
            return [float(x) for x in val]
        if isinstance(val, str):
            parts = [s.strip() for s in val.split(',') if s.strip()]
            return [float(x) for x in parts]
        return [float(val)]

    # --- MODIFICATION START: Formatting Methods ---
    def _to_superscript(self, num):
        """Converts integer numbers to unicode superscript (e.g., 2 -> ²)."""
        # Map normal digits to superscript unicode chars
        mapping = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
        return str(num).translate(mapping)

    def _format_poly(self, coeffs):
        """Turn [1, 2, 3] into 's² + 2s + 3' using unicode."""
        if not coeffs: return "0"
        
        # Remove leading zeros
        while len(coeffs) > 1 and coeffs[0] == 0:
            coeffs.pop(0)
            
        order = len(coeffs) - 1
        terms = []
        
        for i, c in enumerate(coeffs):
            power = order - i
            if c == 0: continue
            
            # 1. Handle Sign
            sign = ""
            if c < 0: sign = "- "
            elif i > 0: sign = "+ " 
            
            abs_c = abs(c)
            
            # 2. Handle Coefficient (hide 1.0 if part of a term like 1s)
            str_c = f"{abs_c:g}" 
            if abs_c == 1 and power > 0:
                str_c = "" 
            
            # 3. Handle Variable s
            str_s = ""
            if power == 1: 
                str_s = "s"
            elif power > 1: 
                str_s = f"s{self._to_superscript(power)}"
            
            # Edge case: Constant 1
            if str_c == "" and str_s == "":
                str_c = "1"
                
            terms.append(f"{sign}{str_c}{str_s}")
            
        result = "".join(terms)
        # Clean up leading "+ " if it exists
        if result.startswith("+ "):
            result = result[2:]
        return result if result else "0"

    def _update_label(self):
        """Updates block name to a 3-line ASCII fraction."""
        try:
            num = self._parse_coeffs(self.params.get("Numerator", [1.0]))
            den = self._parse_coeffs(self.params.get("Denominator", [1.0, 1.0]))
            
            n_str = self._format_poly(num)
            d_str = self._format_poly(den)
            
            # Calculate the width of the fraction bar
            width = max(len(n_str), len(d_str))
            
            # Center the strings using spaces
            # Note: This aligns perfectly with monospaced fonts. 
            # With proportional fonts (like Arial), it's approximate but usually readable.
            n_pad = n_str.center(width)
            d_pad = d_str.center(width)
            
            # Create the bar (using unicode box drawing char or underscores)
            bar = "—" * width 
            
            # Combine into 3 lines
            self.name = f"{n_pad}\n{bar}\n{d_pad}"
        except:
            self.name = "TransferFunction"
    # --- MODIFICATION END ---

    def _update_matrices(self):
        # ... (Existing Logic Unchanged) ...
        num_raw = self._parse_coeffs(self.params.get("Numerator", [1.0]))
        den_raw = self._parse_coeffs(self.params.get("Denominator", [1.0, 1.0]))

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

    def compute_chunk(self, t_vec, dt, context=None):
        # Custom (not the default per-sample compute()-only shim): state
        # must advance sample-by-sample WITHIN this pass for the audio/
        # realtime path to be correct, since this block's dynamics are
        # sequential (each sample's output depends on the previous sample's
        # integrated state). update_state_chunk() below is a no-op so the
        # default chunk shim doesn't try to integrate a second time.
        if dt <= 0:
            return
        self._refresh_matrices_if_needed()

        u_vec = self.inputs["in"].vector_value if "in" in self.inputs else np.zeros(len(t_vec))
        n = len(self.states)
        out = np.zeros(len(t_vec))

        if n == 0:
            out[:] = self._D * u_vec
        else:
            for i in range(len(t_vec)):
                u = float(u_vec[i])
                y = self._D * u
                for j in range(n):
                    y += self._C[j] * self.states[n - 1 - j]
                out[i] = y

                derivatives = self._derivatives_for(u, self.states)
                for j in range(n):
                    self.states[j] += derivatives[j] * dt

        self.outputs["out"].vector_value = out

    def update_state_chunk(self, t_vec, dt, context=None):
        # State was already advanced inline inside compute_chunk() above.
        pass

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