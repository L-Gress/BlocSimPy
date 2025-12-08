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
        "usage": "Control systems to track setpoints and reject disturbances"
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

    def compute(self, t, dt):
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
