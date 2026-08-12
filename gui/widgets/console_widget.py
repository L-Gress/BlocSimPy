"""Interactive Console: a REPL prompt against ScriptManager's single shared
execution environment (see gui/managers/script_manager.py's module
docstring) -- the exact same environment every Script run execs
against, so a variable/function a Script defines is visible here, and
anything typed here is visible to the next Script run, for the life of the
app session. One Console lives on MainWindow (see DockManager.create_
console_dock()), not one per Script tab -- "a single execution environment"
means one shared REPL, not an isolated one per open file.
"""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QTextEdit, QLineEdit
from PySide6.QtGui import QFont
from PySide6.QtCore import Qt


class _CommandInput(QLineEdit):
    """QLineEdit with Up/Down command history, like a shell prompt.

    `history` is the SAME list object ConsoleWidget appends submitted
    commands to -- read fresh on every key press rather than copied, so it
    always reflects the latest command even though this widget doesn't
    itself add to it (ConsoleWidget._on_submit does, then resets
    _history_index via reset_history_cursor())."""

    def __init__(self, history, parent=None):
        super().__init__(parent)
        self._history = history
        self._history_index = len(history)
        self._draft = ""

    def reset_history_cursor(self):
        self._history_index = len(self._history)
        self._draft = ""

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Up:
            if not self._history:
                return
            if self._history_index == len(self._history):
                self._draft = self.text()
            if self._history_index > 0:
                self._history_index -= 1
                self.setText(self._history[self._history_index])
            return
        if event.key() == Qt.Key_Down:
            if self._history_index >= len(self._history):
                return
            self._history_index += 1
            if self._history_index == len(self._history):
                self.setText(self._draft)
            else:
                self.setText(self._history[self._history_index])
            return
        super().keyPressEvent(event)


class ConsoleWidget(QWidget):
    """A VSCode/IPython-style console: scrolling output log + single-line
    command prompt. Lives in a dock (see DockManager.create_console_dock()),
    reachable regardless of which diagram/Script tab is currently active."""

    def __init__(self, main_window, script_manager, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.script_manager = script_manager
        self._history = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        font = QFont("Consolas")
        font.setPointSize(10)

        self.output = QTextEdit()
        self.output.setReadOnly(True)
        self.output.setFont(font)
        self.output.setStyleSheet(
            "background-color: #1e1e1e; color: #d4d4d4; border: 1px solid #3a3a3c;"
        )
        self.output.setPlainText(
            "BlocSimPy Console -- shares its environment with every Script "
            "run: anything you define here or there is visible in "
            "both, for the rest of this session. Type a command and press Enter."
        )
        layout.addWidget(self.output)

        self.input = _CommandInput(self._history)
        self.input.setFont(font)
        self.input.setPlaceholderText(">>> ")
        self.input.setStyleSheet(
            "background-color: #252526; color: #d4d4d4; border: 1px solid #3a3a3c; padding: 3px;"
        )
        self.input.returnPressed.connect(self._on_submit)
        layout.addWidget(self.input)

    def _on_submit(self):
        command = self.input.text()
        if not command.strip():
            return

        self._history.append(command)
        self.input.clear()
        self.input.reset_history_cursor()

        self.output.append(f">>> {command}")
        result = self.script_manager.execute_command(command)
        if result:
            self.output.append(result)

        self._scroll_to_bottom()

    def set_input_enabled(self, enabled):
        """Disable the prompt while a Script is running via the toolbar's
        Run/Stop button (see ToolbarManager.run_script()) -- a Script run
        stays on the GUI thread (the scripting API directly touches
        QGraphicsScene/UIBlock, which isn't safe off it) and cooperatively
        pumps the event loop during a sim() call so the app doesn't look
        frozen, which means a Console command submitted mid-run WOULD
        actually execute right then, re-entrantly, on top of the
        still-running Script -- both exec() against the very same
        persistent_env dict. Re-enabled once the Script finishes."""
        self.input.setEnabled(enabled)

    def log_external(self, label, text):
        """Append output from something other than a command typed here --
        currently just a Script run (see ToolbarManager.run_script()) --
        so the Console reads as one combined log of everything that ran
        in the shared environment, not
        only what was typed directly into this prompt. Works (and keeps
        scrolled to the latest entry) whether or not the dock is currently
        visible, so the log is already there when it's next opened."""
        self.output.append(f"▶ {label}")
        if text:
            self.output.append(text)
        self._scroll_to_bottom()

    def _scroll_to_bottom(self):
        sb = self.output.verticalScrollBar()
        sb.setValue(sb.maximum())
