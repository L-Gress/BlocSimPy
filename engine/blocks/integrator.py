from ..models import BlockModel

class Integrator(BlockModel):
    """Integrator block - integrates signal over time."""
    
    BLOCK_INFO = {
        "description": "Integrates input signal over time (Euler method)",
        "parameters": "Initial Condition",
        "formula": "Standard recursive integration",
        "usage": "Dynamic systems, state estimation",
        "category": "Signal"
    }
    
    def __init__(self):
        super().__init__("Integrator")
        self.add_input("in")
        self.add_output("out")
        self.add_param("InitialCondition", 0.0)
        
        self.state = 0.0
        self.initialized = False
        self._cached_ic = 0.0
        
        # Set a nice label
        self.name = "∫"
        self._cache_params()

    def _cache_params(self):
        try:
            self._cached_ic = float(self.params.get("InitialCondition", 0.0))
        except:
            self._cached_ic = 0.0

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_cache_params"):
            self._cache_params()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._cache_params()

    def compute(self, t, dt, context=None):
        # 1. Initialization Logic
        if not self.initialized:
            self.state = self._cached_ic
            self.initialized = True

        # 2. Set the Output
        self.outputs["out"].value = self.state

    def compute_chunk(self, t_vec, dt, context=None):
        if not self.initialized:
            self.state = self._cached_ic
            self.initialized = True
            
        # Output current state (constant for this step until updated?)
        # BUT: Integrator state changes continuously if there is input.
        # Wait, pure integrator usually outputs state, THEN updates state based on input.
        # So output for the WHOLE chunk should reflect the integration of the input chunk?
        # Yes. y[k] = y[k-1] + u[k-1]*dt (Forward Euler)
        # OR y[k] = y[k-1] + u[k]*dt (Backward Euler)
        # BlockModel structure: compute() sets output based on CURRENT state and inputs.
        # update_state() advances state for NEXT step.
        
        # In current compute(): output = self.state.
        # In current update_state(): self.state += input * dt.
        # This is strictly Forward Euler where y[n] depends on state[n], and state[n+1] depends on u[n].
        
        # So for a chunk:
        # y[0] = state
        # y[1] = state + u[0]*dt
        # y[2] = state + u[0]*dt + u[1]*dt
        # ...
        # y[n] = state + sum(u[0..n-1])*dt
        
        # We need input vector u.
        u_vec = self.inputs["in"].vector_value
        
        import numpy as np
        # Cumulative sum of inputs * dt
        # np.cumsum([a, b, c]) -> [a, a+b, a+b+c]
        # We need [0, a, a+b] * dt + state for output?
        # No, update_state happens AFTER compute.
        # So at step i: output is state_i.
        # state_{i+1} = state_i + u_i * dt.
        
        # So output vector:
        # out[0] = state_0
        # out[1] = state_0 + u[0]*dt
        # out[2] = state_0 + (u[0]+u[1])*dt
        
        # We can construct this with cumsum of u, shifted.
        increments = u_vec * dt
        cum_increments = np.cumsum(increments)
        
        # The output at index i should NOT include increment i.
        # It should include increments 0..i-1.
        # So we shift: [0, inc[0], inc[0]+inc[1], ...]
        
        shifted_cum = np.roll(cum_increments, 1)
        shifted_cum[0] = 0.0
        
        self.outputs["out"].vector_value = self.state + shifted_cum
        
        # The final state for next chunk will be state_0 + sum(all increments)
        # We update self.state in update_state_chunk?
        # If we do logic here, we must coordinate with update_state_chunk.
        # BUT: BlockModel separates compute and update_state.
        # If we do it here, update_state_chunk should effectively do nothing or just sync?
        # Actually, base update_state_chunk iterates.
        
        # For efficiency, Integrator should implement BOTH compute_chunk and update_state_chunk.
        # We'll store the total increment temporarily?
        # Or just do the update in update_state_chunk?
        # The output DOES need the intra-chunk integrated values.
        
        self._temp_total_increment = cum_increments[-1]

    def update_state_chunk(self, t_vec, dt, context=None):
        if hasattr(self, '_temp_total_increment'):
            self.state += self._temp_total_increment
            del self._temp_total_increment
        else:
            # Fallback if compute_chunk wasn't called (unlikely)
            # Implement vector update: state += sum(inputs)*dt
            # But inputs might not be available if cleared? No, they are.
             u_vec = self.inputs["in"].vector_value
             import numpy as np
             self.state += np.sum(u_vec) * dt

    def update_state(self, t, dt, context=None):
        # Perform the integration (Euler: New = Old + Input * TimeStep)
        inp = self.inputs["in"].value if "in" in self.inputs else 0.0
        self.state += float(inp) * dt

    def reset(self):
        """Reset state to Initial Condition on stop/start."""
        self.initialized = False
        self.state = self._cached_ic

    def get_editor_dialog(self, parent=None):
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle("Edit Integrator")
        layout = QFormLayout(dialog)
        
        # Initial Condition Input
        val = self.params.get("InitialCondition", 0.0)
        le = QLineEdit(str(val))
        layout.addRow("Initial Condition:", le)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            try:
                self.params["InitialCondition"] = float(le.text())
            except ValueError:
                self.params["InitialCondition"] = 0.0

            # Refresh the cached initial condition, then reset immediately so
            # the change takes effect if simulation is stopped.
            self._cache_params()
            self.reset()
            original_accept()

        dialog.accept = accept_with_save
        return dialog