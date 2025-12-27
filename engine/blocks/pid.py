from ..models import BlockModel


class PID(BlockModel):
    """Proportional-Integral-Derivative (PID) Controller.
    
    Parameters:
    - "Kp": Proportional gain
    - "Ki": Integral gain
    - "Kd": Derivative gain
    
    The PID output is: u(t) = Kp*e(t) + Ki*∫e(t)dt + Kd*de(t)/dt
    where e(t) is the error (input signal).
    """
    
    BLOCK_INFO = {
        "description": "Proportional-Integral-Derivative controller for feedback control",
        "parameters": "Kp (proportional), Ki (integral), Kd (derivative)",
        "formula": "Output = Kp×e + Ki×∫e + Kd×(de/dt)",
        "usage": "Control systems to track setpoints and reject disturbances",
        "category": "Signal"
    }
    
    def __init__(self):
        super().__init__("PID")
        self.add_input("in")
        self.add_output("out")
        
        # Default parameters
        self.add_param("Kp", 1.0)
        self.add_param("Ki", 0.0)
        self.add_param("Kd", 0.0)
        
        # Internal state: integral accumulator
        self.integral = 0.0
        
        # Previous error for derivative calculation
        self.prev_error = 0.0

    def compute(self, t, dt, context=None):
        """Compute the PID output based on the input error."""
        try:
            kp = float(self.params.get("Kp", 1.0))
            ki = float(self.params.get("Ki", 0.0))
            kd = float(self.params.get("Kd", 0.0))
        except (ValueError, TypeError):
            kp = ki = 1.0
            kd = 0.0

        # Get input (error signal)
        error = float(self.inputs["in"].value) if "in" in self.inputs else 0.0

        # Proportional term
        p_term = kp * error

        # Integral term (accumulate over time)
        self.integral += error * dt
        i_term = ki * self.integral

        # Derivative term (estimated from discrete difference)
        if dt > 0:
            derivative = (error - self.prev_error) / dt
        else:
            derivative = 0.0
        d_term = kd * derivative

        # Total PID output
        output = p_term + i_term + d_term
        self.outputs["out"].value = output

        # Update for next step
        self.prev_error = error

    def compute_chunk(self, t_vec, dt, context=None):
        import numpy as np
        
        # 1. Parse params locally (or cache them for perf)
        kp = float(self.params.get("Kp", 1.0))
        ki = float(self.params.get("Ki", 0.0))
        kd = float(self.params.get("Kd", 0.0))
        
        # 2. Get Input Vector (Error Signal)
        error_vec = self.inputs["in"].vector_value
        
        # 3. Proportional Term (Vectorized)
        p_term = kp * error_vec
        
        # 4. Integral Term (Cumulative Sum)
        # We need to carry over the integral state from the last chunk.
        # cumsum gives the running sum WITHIN this chunk.
        # We add the previous accumulated integral to all elements.
        step_integrals = np.cumsum(error_vec) * dt
        i_term = ki * (self.integral + step_integrals)
        
        # Update state for next chunk
        self.integral += step_integrals[-1]
        
        # 5. Derivative Term (Finite Difference)
        # We need the last sample of the previous chunk to compute the diff for the first sample of this chunk.
        # We can prepend prev_error to error_vec
        extended_error = np.hstack(([self.prev_error], error_vec))
        diffs = np.diff(extended_error)
        
        if dt > 0:
            derivative = diffs / dt
        else:
            derivative = np.zeros_like(error_vec)
            
        d_term = kd * derivative
        
        # Update state for next chunk
        self.prev_error = error_vec[-1]
        
        # 6. Total Output
        self.outputs["out"].vector_value = p_term + i_term + d_term

    def reset(self):
        """Reset internal states."""
        self.integral = 0.0
        self.prev_error = 0.0

    def get_editor_dialog(self, parent=None):
        """Editor dialog for PID parameters."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox, QLabel

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Edit {self.name}")
        layout = QFormLayout(dialog)

        # Instruction label
        info = QLabel(
            "PID Controller Parameters:\n"
            "Enter numeric values for each gain.\n"
            "u(t) = Kp*e(t) + Ki*∫e(t)dt + Kd*de(t)/dt"
        )
        info.setWordWrap(True)
        layout.addRow(info)

        # Parameter input fields
        kp_edit = QLineEdit(str(self.params.get("Kp", 1.0)))
        kp_edit.setPlaceholderText("Proportional gain (e.g. 1.0)")

        ki_edit = QLineEdit(str(self.params.get("Ki", 0.0)))
        ki_edit.setPlaceholderText("Integral gain (e.g. 0.1)")

        kd_edit = QLineEdit(str(self.params.get("Kd", 0.0)))
        kd_edit.setPlaceholderText("Derivative gain (e.g. 0.5)")

        layout.addRow("Kp (Proportional):", kp_edit)
        layout.addRow("Ki (Integral):", ki_edit)
        layout.addRow("Kd (Derivative):", kd_edit)

        # OK/Cancel buttons
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        # Custom accept handler to save parameters
        original_accept = dialog.accept

        def accept_with_save():
            try:
                self.params["Kp"] = float(kp_edit.text())
                self.params["Ki"] = float(ki_edit.text())
                self.params["Kd"] = float(kd_edit.text())
                self.reset()
                original_accept()
            except ValueError:
                from PySide6.QtWidgets import QMessageBox
                QMessageBox.warning(dialog, "Invalid Input", "Please enter valid numeric values.")

        dialog.accept = accept_with_save
        return dialog
