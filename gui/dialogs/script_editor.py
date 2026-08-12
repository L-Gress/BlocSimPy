import os
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTextEdit, QHBoxLayout, QPushButton, QMessageBox
from .python_highlighter import PythonHighlighter
from config import theme as theme_config

# Editor surface colors per app theme -- kept here (not read from the QSS)
# since QTextEdit's *content* colors (background/selection) need to be set
# directly for the syntax highlighter's own foreground colors to read
# correctly against them; see apply_theme() and PythonHighlighter.set_mode().
_EDITOR_STYLE = {
    "light": (
        "QTextEdit { background-color: %s; color: %s; "
        "border: 1px solid %s; selection-background-color: #cce5ff; }"
    ) % (theme_config.LIGHT["ELEVATED"], theme_config.LIGHT["TEXT"], theme_config.LIGHT["BORDER"]),
    "dark": (
        "QTextEdit { background-color: %s; color: %s; "
        "border: 1px solid %s; selection-background-color: #264f78; }"
    ) % (theme_config.DARK["ELEVATED"], theme_config.DARK["TEXT"], theme_config.DARK["BORDER"]),
}


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
    not one separate log per open Script tab.

    IDE-style syntax highlighting (see gui/dialogs/python_highlighter.py)
    colors keywords/strings/comments/numbers, plus BlocSimPy's own
    scripting API names (add_block, sim, ...) in their own color -- in
    whichever palette (light/dark) matches the app-wide theme at the time
    (see gui/managers/theme_manager.py), defaulting to light like the rest
    of the app. apply_theme() re-colors an already-open tab in place when
    the user toggles the theme."""

    def __init__(self, main_window, script_manager, file_path, content, mode="light"):
        super().__init__()
        self.main_window = main_window
        self.script_manager = script_manager
        self.file_path = file_path
        self.mode = mode

        layout = QVBoxLayout(self)

        # Editor Area
        layout.addWidget(QLabel("Python Script:"))

        # Use Monospace font
        font = self.font()
        font.setFamily("Consolas")
        font.setPointSize(10)

        self.editor = QTextEdit()
        self.editor.setFont(font)
        self.editor.setStyleSheet(_EDITOR_STYLE[self.mode])
        self.editor.setPlainText(content)
        self.editor.document().setModified(False)
        self.editor.document().modificationChanged.connect(self._on_modified_changed)
        layout.addWidget(self.editor)

        # Syntax highlighting -- keywords/builtins/strings/comments/numbers,
        # plus BlocSimPy's own scripting API names in their own color (see
        # PythonHighlighter). Reads _build_api()'s key set the same
        # side-effect-free way GlobalsWidget does, so this can't drift out
        # of sync with the real API by hand-duplicating its name list here.
        api_names = script_manager._build_api(lambda *args: None).keys()
        self.highlighter = PythonHighlighter(self.editor.document(), api_names=api_names, mode=self.mode)

        # Buttons -- just navigation; Run (F5)/Save (Ctrl+S) are the
        # shared toolbar actions (see class docstring).
        btn_layout = QHBoxLayout()

        btn_back = QPushButton("← Back to Diagram")
        btn_back.clicked.connect(lambda: self.main_window.show_diagram_editor())

        btn_layout.addStretch()
        btn_layout.addWidget(btn_back)

        layout.addLayout(btn_layout)

    def apply_theme(self, mode):
        """Re-color this already-open tab's editor + highlighter in place --
        called on every open Script tab when the user toggles the app-wide
        theme (see gui/managers/theme_manager.py)."""
        self.mode = "dark" if mode == "dark" else "light"
        self.editor.setStyleSheet(_EDITOR_STYLE[self.mode])
        self.highlighter.set_mode(self.mode)

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
