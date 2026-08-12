import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QMessageBox


class ScriptEditorWidget(QWidget):
    """Edit and run a Script from User Space. Lives in its own tab in the
    main window's central area (not a separate dialog window) -- multiple
    Scripts can be open as separate tabs at once, see
    MainWindow.open_script_tab()/update_script_tab_title(). Always bound
    to the file it was opened from (created via
    UserSpaceWidget.create_script(), or opened by double-clicking it in
    the tree) -- Save writes straight back to that path, so scripts stay
    organized in User Space rather than scattered wherever a native
    file-save dialog last pointed.

    Running/saving this tab is done via the SAME toolbar Run/Stop and Save
    actions a Diagram tab uses (see MainWindow.active_script_widget() and
    ToolbarManager) -- not a Run Script/Save button of its own, so there's
    one consistent place for both regardless of which kind of tab is
    focused. Has no Output pane of its own either -- Run's output goes to
    the Console dock instead (see ToolbarManager.run_script()), which is
    the single combined log for every Script run and every typed command,
    not one separate log per open Script tab."""

    def __init__(self, main_window, script_manager, file_path, content):
        super().__init__()
        self.main_window = main_window
        self.script_manager = script_manager
        self.file_path = file_path

        layout = QVBoxLayout(self)

        # Editor Area
        layout.addWidget(QLabel("Python Script:"))

        # Use Monospace font
        font = self.font()
        font.setFamily("Consolas")
        font.setPointSize(10)

        self.editor = QTextEdit()
        self.editor.setFont(font)
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)
        self.editor.document().modificationChanged.connect(self._on_modified_changed)
        layout.addWidget(self.editor)

        # Buttons -- just navigation; Run (F5)/Save (Ctrl+S) are the
        # shared toolbar actions (see class docstring).
        btn_layout = QHBoxLayout()

        btn_back = QPushButton("← Back to Diagram")
        btn_back.clicked.connect(lambda: self.main_window.show_diagram_editor())

        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)

        layout.addLayout(btn_layout)

    def _on_modified_changed(self, modified):
        """Reflect unsaved edits in this Script's tab label (e.g.
        'demo.py •'), same convention most code editors use."""
        if hasattr(self.main_window, "update_script_tab_title"):
            self.main_window.update_script_tab_title(self.file_path, modified)

    def _status(self, message):
        """Routine, non-blocking confirmation (saved/loaded/...), same
        status-bar convention SceneManager uses for Diagram Save."""
        if hasattr(self.main_window, "show_status"):
            self.main_window.show_status(message)

    def save_script(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self._status(f"Saved {os.path.basename(self.file_path)}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to save: {e}")

    def confirm_discard(self):
        """Ask before this tab is closed with unsaved edits still in the
        editor. Returns True if it's safe to proceed (no changes,
        discarded, or saved successfully)."""
        if not self.editor.document().isModified():
            return True

        reply = QMessageBox.question(
            self, "Unsaved Changes",
            f"'{os.path.basename(self.file_path)}' has unsaved changes. Save them before continuing?",
            QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
            QMessageBox.Save,
        )
        if reply == QMessageBox.Save:
            self.save_script()
            return not self.editor.document().isModified()
        return reply == QMessageBox.Discard
