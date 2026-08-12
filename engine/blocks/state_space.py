import numpy as np
from ..models import BlockModel


def _parse_matrix(text):
    rows = [r.strip() for r in text.split(';') if r.strip()]
    return [[float(p) for p in row.replace(',', ' ').split()] for row in rows]


def _format_matrix(value):
    return "; ".join(" ".join(str(v) for v in row) for row in value)


def _parse_vector(text):
    return [float(p) for p in text.replace(',', ' ').replace(';', ' ').split()]


def _format_vector(value):
    return " ".join(str(v) for v in value)


class StateSpace(BlockModel):
    """SISO continuous-time State-Space model: x' = Ax + Bu, y = Cx + Du.

    Alongside TransferFunction (a single numerator/denominator polynomial
    pair), this lets dynamics be specified directly as A/B/C/D matrices --
    useful when a system is more naturally expressed that way (e.g. derived
    from a textbook/toolbox), without converting to a transfer function
    first. Implements get_derivative()/get_state()/set_state() (see
    engine.simulation.solvers) so it participates in RK4 like TransferFunction.
    """

    BLOCK_INFO = {
        "description": "SISO continuous-time state-space model: x' = Ax + Bu, y = Cx + Du",
        "parameters": "A (n x n), B (n x 1), C (1 x n), D (scalar)",
        "formula": "x' = A x + B u;  y = C x + D u",
        "usage": "Model linear systems directly from state-space matrices instead of a transfer function polynomial pair.",
        "category": "Signal"
    }

    def __init__(self):
        super().__init__("StateSpace")
        self.add_input("in")
        self.add_output("out")

        # Default matches TransferFunction's default H(s) = 1/(s+1).
        self.add_param("A", [[-1.0]])
        self.add_param("B", [1.0])
        self.add_param("C", [1.0])
        self.add_param("D", 0.0)

        self.states = [0.0]
        self._cache_key = None
        self._A = np.array([[-1.0]])
        self._B = np.array([1.0])
        self._C = np.array([1.0])
        self._D = 0.0

    def _refresh_matrices_if_needed(self):
        current = (str(self.params.get("A")), str(self.params.get("B")),
                   str(self.params.get("C")), str(self.params.get("D")))
        if current != self._cache_key:
            self._update_matrices()
            self._cache_key = current

    @property
    def has_direct_feedthrough(self):
        """Live, not a fixed class attribute -- see TransferFunction's
        identical property for the full rationale. D == 0 (this block's own
        default) means no direct feedthrough, so a loop closed through it
        is well-defined and must not be flagged as an algebraic loop."""
        self._refresh_matrices_if_needed()
        return self._D != 0

    def _update_matrices(self):
        A_raw = self.params.get("A", [[-1.0]])
        B_raw = self.params.get("B", [1.0])
        C_raw = self.params.get("C", [1.0])
        D_raw = self.params.get("D", 0.0)

        try:
            A = np.array(A_raw, dtype=float)
            if A.ndim != 2 or A.shape[0] != A.shape[1] or A.shape[0] == 0:
                raise ValueError
        except (TypeError, ValueError):
            # Fall back to a harmless 1-state system rather than crash on
            # bad input, consistent with this codebase's general philosophy.
            A = np.array([[-1.0]])
        n = A.shape[0]

        def as_vector(raw):
            try:
                v = np.array(raw, dtype=float).flatten()
            except (TypeError, ValueError):
                v = np.zeros(n)
            if v.size == n:
                return v
            if v.size > n:
                return v[:n]
            return np.concatenate([v, np.zeros(n - v.size)])

        B = as_vector(B_raw)
        C = as_vector(C_raw)
        try:
            D = float(D_raw)
        except (TypeError, ValueError):
            D = 0.0

        self._A = A
        self._B = B
        self._C = C
        self._D = D

        if len(self.states) != n:
            self.states = [0.0] * n

    def compute(self, t, dt, context=None):
        # Output only; state integration happens in update_state() (Euler)
        # or externally via get_derivative()/get_state()/set_state() (RK4) --
        # same split as TransferFunction/Integrator.
        self._refresh_matrices_if_needed()
        u = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        x = np.array(self.states, dtype=float)
        y = float(np.dot(self._C, x) + self._D * u)
        self.outputs["out"].value = y

    def update_state(self, t, dt, context=None):
        if dt <= 0:
            return
        deriv = self.get_derivative(t, dt)
        for i in range(len(self.states)):
            self.states[i] += deriv[i] * dt

    def get_derivative(self, t, dt):
        self._refresh_matrices_if_needed()
        u = float(self.inputs["in"].value) if "in" in self.inputs else 0.0
        x = np.array(self.states, dtype=float)
        return self._A @ x + self._B * u

    def get_state(self):
        return np.array(self.states, dtype=float)

    def set_state(self, vec):
        self.states = [float(v) for v in vec]

    def reset(self):
        self.states = [0.0] * len(self.states)

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLabel, QDialogButtonBox
        from gui.widgets.param_value_editor import ParamValueEditor, PARSE_ERROR

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit State-Space")
        layout = QFormLayout(dialog)

        info = QLabel(
            "SISO continuous-time state-space model: x' = Ax + Bu, y = Cx + Du.\n"
            "A: rows separated by ';', values by space/comma (e.g. '0 1; -2 -3').\n"
            "B, C: space/comma-separated values (length = A's order). D: a scalar.\n"
            "Any of these can instead be a variable name, binding it to a "
            "global variable holding the whole matrix/vector/scalar."
        )
        info.setWordWrap(True)
        layout.addRow(info)

        a_edit = ParamValueEditor(self.params.get("A", [[-1.0]]), parse=_parse_matrix, format_fn=_format_matrix)
        b_edit = ParamValueEditor(self.params.get("B", [1.0]), parse=_parse_vector, format_fn=_format_vector)
        c_edit = ParamValueEditor(self.params.get("C", [1.0]), parse=_parse_vector, format_fn=_format_vector)
        d_edit = ParamValueEditor(self.params.get("D", 0.0))

        layout.addRow("A:", a_edit)
        layout.addRow("B:", b_edit)
        layout.addRow("C:", c_edit)
        layout.addRow("D:", d_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            # A bad edit in one field leaves just that one param untouched
            # (see ParamValueEditor.PARSE_ERROR) rather than discarding the
            # other three or crashing the dialog.
            for key, editor in (("A", a_edit), ("B", b_edit), ("C", c_edit), ("D", d_edit)):
                value = editor.get_value()
                if value is not PARSE_ERROR:
                    self.params[key] = value

            self._cache_key = None
            self.reset()
            original_accept()

        dialog.accept = accept_with_save
        return dialog
