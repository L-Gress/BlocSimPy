"""Dialog shown before Run to surface issues from SimulationEngine.check_diagram()
('Update Diagram' pre-flight check)."""
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QListWidget,
                               QListWidgetItem, QLabel, QPushButton)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor


class DiagramCheckDialog(QDialog):
    """Shows the issues found by SimulationEngine.check_diagram_detailed().

    If any issue is blocking ("ERROR:"-prefixed, e.g. an algebraic loop),
    only a dismiss path is offered -- Run cannot proceed until it's fixed.
    Otherwise (only "WARNING:"-prefixed issues, e.g. unconnected inputs)
    the user can choose to Run Anyway.

    Double-clicking an issue selects and centers the offending block(s) on
    the canvas, so tracking one down in a large diagram doesn't mean
    hunting for it by name.
    """

    def __init__(self, issues, parent=None, main_window=None):
        super().__init__(parent)
        self.main_window = main_window
        self.setWindowTitle("Diagram Check")
        self.resize(480, 320)
        self.blocking = any(i["level"] == "ERROR" for i in issues)

        layout = QVBoxLayout(self)
        header = ("This diagram has errors and cannot run:" if self.blocking
                   else "This diagram has some warnings:")
        layout.addWidget(QLabel(header))

        list_widget = QListWidget()
        for issue in issues:
            is_error = issue["level"] == "ERROR"
            item = QListWidgetItem(("⛔ " if is_error else "⚠ ") + issue["message"])
            item.setForeground(QColor("#ff3b30") if is_error else QColor("#ff9500"))
            item.setData(Qt.UserRole, issue.get("blocks", []))
            list_widget.addItem(item)
        if self.main_window is not None:
            list_widget.setToolTip("Double-click an issue to locate the block(s) involved.")
            list_widget.itemDoubleClicked.connect(self._locate_blocks)
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

    def _locate_blocks(self, item):
        """Select the named block(s) on the canvas and center the view on
        them, so the user can find what an issue is talking about without
        hunting through the diagram by eye."""
        names = item.data(Qt.UserRole) or []
        if not names or self.main_window is None:
            return

        scene_manager = getattr(self.main_window, "scene_manager", None)
        scene = getattr(self.main_window, "scene", None)
        view = getattr(self.main_window, "view", None)
        if scene_manager is None or scene is None:
            return

        matches = [
            ui_block for ui_block in scene_manager.blocks_ui
            if ui_block.model.params.get("BlockName", ui_block.model.name) in names
        ]
        if not matches:
            return

        scene.clearSelection()
        for ui_block in matches:
            ui_block.setSelected(True)

        if view is not None:
            rect = matches[0].sceneBoundingRect()
            for ui_block in matches[1:]:
                rect = rect.united(ui_block.sceneBoundingRect())
            view.centerOn(rect.center())
