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
    file-save dialog last pointed."""

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

        # Output Area
        layout.addWidget(QLabel("Output:"))
        self.output_console = QTextEdit()
        self.output_console.setReadOnly(True)
        self.output_console.setMaximumHeight(150)
        self.output_console.setStyleSheet(
            "background-color: #f6f6f7; color: #1d7a3c; font-family: Consolas;"
        )
        layout.addWidget(self.output_console)

        # Buttons
        btn_layout = QHBoxLayout()

        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_script)

        btn_run = QPushButton("Run Script")
        btn_run.setDefault(True)  # picks up the accent-blue QPushButton:default styling
        btn_run.clicked.connect(self.run_script)

        btn_clear = QPushButton("Clear Output")
        btn_clear.clicked.connect(self.output_console.clear)

        btn_back = QPushButton("← Back to Diagram")
        btn_back.clicked.connect(lambda: self.main_window.show_diagram_editor())

        btn_layout.addWidget(btn_save)
        btn_layout.addWidget(btn_run)
        btn_layout.addWidget(btn_clear)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)

        layout.addLayout(btn_layout)

    def _on_modified_changed(self, modified):
        """Reflect unsaved edits in this Script's tab label (e.g.
        'demo.py •'), same convention most code editors use."""
        if hasattr(self.main_window, "update_script_tab_title"):
            self.main_window.update_script_tab_title(self.file_path, modified)

    def save_script(self):
        try:
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self.editor.toPlainText())
            self.editor.document().setModified(False)
            self.output_console.append(f"Saved: {self.file_path}")
        except Exception as e:
            self.output_console.append(f"Error saving file: {e}")

    def run_script(self):
        """Execute the current script."""
        script_content = self.editor.toPlainText()

        result = self.script_manager.execute_script(script_content)
        self.output_console.append(">>> Execution:")
        self.output_console.append(result)
        self.output_console.append("-" * 30)
        # Scroll to bottom
        sb = self.output_console.verticalScrollBar()
        sb.setValue(sb.maximum())

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
