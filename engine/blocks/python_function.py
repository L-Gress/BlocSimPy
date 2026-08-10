"""Python Function block: arbitrary user Python code executed once per
simulation timestep, reading/writing its own ports -- the per-timestep
analogue of Simulink's MATLAB Function block.

Distinct from the existing Script Editor (gui/dialogs/script_editor.py +
gui/managers/script_manager.py): that console runs a script ONCE, on
demand, against the live GUI scene (add/remove blocks, set params, etc.).
This block instead runs user code every timestep, INSIDE the simulation,
with access only to its own ports/state -- it has no access to the scene.

Like the Script Editor's ScriptManager.execute_script (which already runs
via a bare exec() with no sandboxing), this is a local, single-user desktop
app the user runs themselves, so no sandboxing is implemented here either --
the design concern is correctness (caching, not crashing the run), not a
security boundary.
"""
from ..models import BlockModel


DEFAULT_CODE = """# Available: in1..inN, t, dt, and a persistent dict `state`
# (carried across timesteps -- use it for anything that needs memory).
# Set out1..outN before the end of the script.
state.setdefault('count', 0)
state['count'] += 1

out1 = in1 * 2.0
"""


class PythonFunction(BlockModel):
    """Runs user Python code once per timestep. Ports are dynamic
    (NumInputs/NumOutputs), like Mux/Demux/Scope."""

    BLOCK_INFO = {
        "description": "Runs custom Python code once per simulation timestep",
        "parameters": "Code (Python source), NumInputs, NumOutputs",
        "formula": "Locals available to the code: in1..inN, t, dt, state (persistent dict); set out1..outN",
        "usage": "Arbitrary per-step logic that doesn't fit an existing block. Different from the Script Editor console, which runs once on demand against the whole scene, not per-timestep against a single block's ports.",
        "category": "Structure"
    }

    def __init__(self):
        super().__init__("Python Function")
        self.add_param("Code", DEFAULT_CODE)
        self.add_param("NumInputs", 1)
        self.add_param("NumOutputs", 1)

        self._state = {}
        self._last_error = None
        self._compiled = None
        self._cache_key = None

        self.needs_port_refresh = False
        self.refresh_io_ports()

    def refresh_io_ports(self):
        num_in = max(0, min(16, int(self.params.get("NumInputs", 1))))
        num_out = max(1, min(16, int(self.params.get("NumOutputs", 1))))

        current_in = len(self.inputs)
        if num_in > current_in:
            for i in range(current_in + 1, num_in + 1):
                self.add_input(f"in{i}")
        elif num_in < current_in:
            for i in range(num_in + 1, current_in + 1):
                name = f"in{i}"
                if name in self.inputs:
                    del self.inputs[name]

        current_out = len(self.outputs)
        if num_out > current_out:
            for i in range(current_out + 1, num_out + 1):
                self.add_output(f"out{i}")
        elif num_out < current_out:
            for i in range(num_out + 1, current_out + 1):
                name = f"out{i}"
                if name in self.outputs:
                    del self.outputs[name]

        self.params["NumInputs"] = num_in
        self.params["NumOutputs"] = num_out

    def _refresh_compiled_if_needed(self):
        code = self.params.get("Code", "")
        if code != self._cache_key:
            try:
                self._compiled = compile(code, "<PythonFunction>", "exec")
                self._last_error = None
            except SyntaxError as e:
                self._compiled = None
                self._last_error = f"SyntaxError: {e}"
            self._cache_key = code

    def compute(self, t, dt, context=None):
        self._refresh_compiled_if_needed()
        if self._compiled is None:
            # Bad code (syntax error) -- hold last outputs rather than
            # crashing the run; the error is visible via the editor dialog's
            # Test Run and self._last_error.
            return

        local_scope = {"t": t, "dt": dt, "state": self._state}
        for name in self.inputs:
            local_scope[name] = self.inputs[name].value
        for name in self.outputs:
            local_scope[name] = self.outputs[name].value  # last value, in case the script doesn't touch it

        try:
            import math
            exec(self._compiled, {"__builtins__": __builtins__, "math": math}, local_scope)
        except Exception as e:
            # Consistent with SimulationEngine.run()'s existing contract:
            # one exploding block reports failure without corrupting other
            # blocks' state. A per-call exception here just holds last
            # outputs rather than propagating and killing the whole run --
            # the error is still visible via self._last_error.
            self._last_error = f"{type(e).__name__}: {e}"
            return

        self._last_error = None
        for name in self.outputs:
            try:
                self.outputs[name].value = float(local_scope.get(name, 0.0))
            except (TypeError, ValueError):
                self.outputs[name].value = 0.0

    def reset(self):
        self._state = {}

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
                                       QSpinBox, QPushButton, QDialogButtonBox)

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Python Function")
        dialog.resize(560, 520)
        layout = QVBoxLayout(dialog)

        ports_row = QHBoxLayout()
        ports_row.addWidget(QLabel("Inputs:"))
        in_spin = QSpinBox()
        in_spin.setRange(0, 16)
        in_spin.setValue(int(self.params.get("NumInputs", 1)))
        ports_row.addWidget(in_spin)
        ports_row.addWidget(QLabel("Outputs:"))
        out_spin = QSpinBox()
        out_spin.setRange(1, 16)
        out_spin.setValue(int(self.params.get("NumOutputs", 1)))
        ports_row.addWidget(out_spin)
        ports_row.addStretch()
        layout.addLayout(ports_row)

        layout.addWidget(QLabel("Code (runs once per timestep; set out1..outN):"))
        font = dialog.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        editor = QTextEdit()
        editor.setFont(font)
        editor.setPlainText(self.params.get("Code", DEFAULT_CODE))
        layout.addWidget(editor)

        layout.addWidget(QLabel("Test Run output:"))
        output_console = QTextEdit()
        output_console.setReadOnly(True)
        output_console.setMaximumHeight(120)
        output_console.setStyleSheet("background-color: #222; color: #0f0; font-family: Consolas;")
        layout.addWidget(output_console)

        def test_run():
            try:
                compiled = compile(editor.toPlainText(), "<PythonFunction Test>", "exec")
            except SyntaxError as e:
                output_console.append(f"SyntaxError: {e}")
                return

            n_in = in_spin.value()
            n_out = out_spin.value()
            local_scope = {"t": 0.0, "dt": 0.01, "state": {}}
            for i in range(1, n_in + 1):
                local_scope[f"in{i}"] = 0.0
            for i in range(1, n_out + 1):
                local_scope[f"out{i}"] = 0.0

            try:
                import math
                exec(compiled, {"__builtins__": __builtins__, "math": math}, local_scope)
            except Exception as e:
                output_console.append(f"{type(e).__name__}: {e}")
                return

            outputs = ", ".join(f"out{i}={local_scope.get(f'out{i}')}" for i in range(1, n_out + 1))
            output_console.append(f"OK -- {outputs}")

        btn_test = QPushButton("▶ Test Run (t=0, dt=0.01, inputs=0)")
        btn_test.clicked.connect(test_run)
        layout.addWidget(btn_test)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)

        original_accept = dialog.accept

        def accept_with_save():
            self.params["Code"] = editor.toPlainText()
            self.params["NumInputs"] = in_spin.value()
            self.params["NumOutputs"] = out_spin.value()
            self.refresh_io_ports()
            self.needs_port_refresh = True
            self._cache_key = None
            original_accept()

        dialog.accept = accept_with_save
        return dialog
