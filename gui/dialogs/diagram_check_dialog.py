"""Dialog shown before Run to surface issues from SimulationEngine.check_diagram()
('Update Diagram' pre-flight check)."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                               QListWidgetItem, QLabel, QPushButton)
from PySide6.QtGui import QColor


class DiagramCheckDialog(QDialog):
    """Shows the issues found by SimulationEngine.check_diagram().

    If any issue is blocking ("ERROR:"-prefixed, e.g. an algebraic loop),
    only a dismiss path is offered -- Run cannot proceed until it's fixed.
    Otherwise (only "WARNING:"-prefixed issues, e.g. unconnected inputs)
    the user can choose to Run Anyway.
    """

    def __init__(self, issues, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Diagram Check")
        self.resize(480, 320)
        self.blocking = any(i.startswith("ERROR:") for i in issues)

        layout = QVBoxLayout(self)
        header = ("This diagram has errors and cannot run:" if self.blocking
                   else "This diagram has some warnings:")
        layout.addWidget(QLabel(header))

        list_widget = QListWidget()
        for issue in issues:
            is_error = issue.startswith("ERROR:")
            text = issue.split(":", 1)[-1].strip()
            item = QListWidgetItem(("⛔ " if is_error else "⚠ ") + text)
            item.setForeground(QColor("#ff3b30") if is_error else QColor("#ff9500"))
            list_widget.addItem(item)
        layout.addWidget(list_widget)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        if self.blocking:
            btn_ok = QPushButton("OK")
            btn_ok.clicked.connect(self.reject)
            btn_layout.addWidget(btn_ok)
        else:
            btn_cancel = QPushButton("Cancel")
            btn_cancel.clicked.connect(self.reject)
            btn_run = QPushButton("Run Anyway")
            btn_run.setDefault(True)
            btn_run.clicked.connect(self.accept)
            btn_layout.addWidget(btn_cancel)
            btn_layout.addWidget(btn_run)
        layout.addLayout(btn_layout)
