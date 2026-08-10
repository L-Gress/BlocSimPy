from ..models import BlockModel
from ._poly_utils import parse_coeffs, format_fraction_label


class DiscreteTransferFunction(BlockModel):
    """Discrete-time (z-domain) transfer function, implemented directly as
    a difference equation (Direct Form II Transposed) -- unlike
    TransferFunction, which models a continuous H(s) and discretizes it ad
    hoc via Euler integration each step, this block IS the discrete system:
    no continuous approximation involved.

    H(z) = (b0 + b1*z^-1 + ... + bN*z^-N) / (a0 + a1*z^-1 + ... + aN*z^-N)

    The simulation's own dt is used as the (implicit) sample period -- this
    codebase doesn't support independent per-block sample rates, so unlike
    Simulink's Discrete Transfer Fcn, there's no separate "sample time"
    parameter. This is a deliberate v1 scope cut.

    Like Delay, all state handling happens inside compute() itself (a pure
    discrete update, not an ODE) -- no get_derivative()/RK4 hook, and no
    custom compute_chunk() override is needed since the default per-sample
    emulation shim already interleaves state correctly.
    """

    BLOCK_INFO = {
        "description": "Discrete-time (z-domain) transfer function via a difference equation",
        "parameters": "Numerator coefficients b, Denominator coefficients a (both in z^-1 form, comma-separated)",
        "formula": "H(z) = (b0 + b1 z^-1 + ...) / (a0 + a1 z^-1 + ...); sample period = simulation dt",
        "usage": "Model discrete filters/controllers designed directly in the z-domain.",
        "category": "Signal"
    }

    def __init__(self):
        super().__init__("DiscreteTransferFunction")
        self.add_input("in")
        self.add_output("out")

        # Default: simple 1-pole discrete low-pass, y[n] = 0.5*x[n] + 0.5*y[n-1]
        self.add_param("Numerator", [0.5])
        self.add_param("Denominator", [1.0, -0.5])

        self.w = []  # Direct Form II Transposed delay line
        self._cache_key = None
        self._b = [0.5]
        self._a = [1.0]
        self._update_label()

    def _refresh_if_needed(self):
        current = (str(self.params.get("Numerator")), str(self.params.get("Denominator")))
        if current != self._cache_key:
            self._update_coeffs()
            self._cache_key = current

    @property
    def has_direct_feedthrough(self):
        """Live, not a fixed class attribute -- see TransferFunction's
        identical property for the full rationale. b0 == 0 means no direct
        feedthrough, so a loop closed through it is well-defined and must
        not be flagged as an algebraic loop."""
        self._refresh_if_needed()
        return self._b[0] != 0 if self._b else False

    def _update_coeffs(self):
        b_raw = parse_coeffs(self.params.get("Numerator", [0.5]))
        a_raw = parse_coeffs(self.params.get("Denominator", [1.0]))
        if not a_raw:
            a_raw = [1.0]
        a0 = a_raw[0] if a_raw[0] != 0 else 1.0

        a = [x / a0 for x in a_raw]
        b = [x / a0 for x in b_raw]

        order = max(len(a), len(b)) - 1
        if order < 0:
            order = 0
        b = b + [0.0] * (order + 1 - len(b))
        a = a + [0.0] * (order + 1 - len(a))

        self._b = b
        self._a = a
        if len(self.w) != order:
            self.w = [0.0] * order

    def compute(self, t, dt, context=None):
        self._refresh_if_needed()
        x = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        n = len(self.w)
        b, a = self._b, self._a

        y = b[0] * x + (self.w[0] if n > 0 else 0.0)

        new_w = [0.0] * n
        for i in range(n):
            feed = b[i + 1] * x - a[i + 1] * y
            nxt = self.w[i + 1] if i + 1 < n else 0.0
            new_w[i] = feed + nxt
        self.w = new_w

        self.outputs["out"].value = y

    def reset(self):
        self.w = [0.0] * len(self.w)

    def _update_label(self):
        try:
            num = parse_coeffs(self.params.get("Numerator", [0.5]))
            den = parse_coeffs(self.params.get("Denominator", [1.0]))
            self.name = format_fraction_label(num, den, variable="z")
        except:
            self.name = "DiscreteTF"

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QLabel

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Discrete Transfer Function")
        layout = QFormLayout(dialog)

        info = QLabel(
            "Discrete-time (z-domain) Transfer Function.\n"
            "Format: coefficients of z^-1 in ascending order (b0, b1, ...).\n"
            "Sample period = the simulation's own time step (dt)."
        )
        info.setWordWrap(True)
        layout.addRow(info)

        num_edit = QLineEdit(", ".join(str(x) for x in self.params.get("Numerator", [0.5])))
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
            self._update_label()
            original_accept()

        dialog.accept = accept_with_save
        return dialog
