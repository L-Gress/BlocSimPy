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
        "usage": "Model linear systems, filters, controllers (PID, lead-lag, etc.)"
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

    def compute(self, t, dt):
        # ... (Existing Logic Unchanged) ...
        if dt <= 0: return

        current_params = (str(self.params["Numerator"]), str(self.params["Denominator"]))
        if current_params != self._cache_key:
            self._update_matrices()
            self._cache_key = current_params

        u = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        n = len(self.states)

        if n == 0:
            self.outputs["out"].value = self._D * u
            return

        derivatives = [0.0] * n
        for i in range(n - 1):
            derivatives[i] = self.states[i+1]
        
        last_dot = u
        for i in range(n):
            last_dot += self._A_row[i] * self.states[i]
        derivatives[n-1] = last_dot

        y = self._D * u
        for i in range(n):
            y += self._C[i] * self.states[n - 1 - i]

        self.outputs["out"].value = y

        for i in range(n):
            self.states[i] += derivatives[i] * dt

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