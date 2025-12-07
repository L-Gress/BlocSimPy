from ..models import BlockModel


class Constant(BlockModel):
    """Outputs a constant value."""
    def __init__(self):
        super().__init__("Constant")
        self.add_output("out")
        self.add_param("Value", 1.0)

    def compute(self, t, dt):
        val = float(self.params["Value"])
        self.outputs["out"].value = val

    def get_editor_dialog(self, parent=None):
        """Return generic parameter editor dialog."""
        from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QDialogButtonBox

        dialog = QDialog(parent)
        dialog.setWindowTitle(f"Edit {self.name}")
        layout = QFormLayout(dialog)
        widgets = {}

        for key, val in self.params.items():
            le = QLineEdit(str(val))
            layout.addRow(key, le)
            widgets[key] = le

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addRow(btns)

        original_accept = dialog.accept

        def accept_with_save():
            for key, le in widgets.items():
                old_val = self.params[key]
                new_str = le.text()
                try:
                    if isinstance(old_val, float) or isinstance(old_val, int):
                        self.params[key] = float(new_str)
                    else:
                        self.params[key] = new_str
                except:
                    self.params[key] = new_str
            original_accept()

        dialog.accept = accept_with_save
        return dialog
