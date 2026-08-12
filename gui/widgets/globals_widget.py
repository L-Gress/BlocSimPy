"""Global Variables dock: a live, read-only table of every name currently
defined in the shared scripting environment (see gui/managers/
script_manager.py's module docstring) -- what a Script run or a
Console command has defined so far this session (a plain `x = 2` is all
it takes; persistent_env IS the global variable namespace, see
_GlobalVariablesView).

The API functions _build_api() injects (add_block, sim, np, ...) are
deliberately left out -- this table is for what YOU defined, the same
idea as dir() hiding dunders. Clear All here (or the toolbar/menu's Clear
Global Variables) wipes it via ScriptManager.clear_globals().

Auto-refreshes on a timer while the dock is visible (see _AUTO_REFRESH_MS)
rather than only on open/Refresh-click: persistent_env is a plain dict
with no change notification to hook into, and a script run, a Console
command, or a param editor declaring a new variable can all change it
from well outside this widget -- polling is what keeps the table from
going stale without wiring a signal through every one of those call sites.
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QLineEdit, QHeaderView, QMessageBox
)
from PySide6.QtCore import QTimer

_AUTO_REFRESH_MS = 500


class GlobalsWidget(QWidget):
    """Name/Type/Value table over ScriptManager.persistent_env. Lives in a
    dock (see DockManager.create_globals_dock()), reachable regardless of
    which diagram/Script tab is currently active -- same shape as
    ConsoleWidget."""

    def __init__(self, main_window, script_manager, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.script_manager = script_manager
        self._last_snapshot = None
        self._search_text = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header_row = QHBoxLayout()
        self.count_label = QLabel("0 variables")
        header_row.addWidget(self.count_label)
        header_row.addStretch()
        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_clicked)
        header_row.addWidget(clear_btn)
        layout.addLayout(header_row)

        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search variables...")
        self.search_edit.textChanged.connect(self._on_search_changed)
        layout.addWidget(self.search_edit)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Type", "Value"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table)

        self._timer = QTimer(self)
        self._timer.setInterval(_AUTO_REFRESH_MS)
        self._timer.timeout.connect(self._auto_refresh)

        self.refresh()

    def showEvent(self, event):
        super().showEvent(event)
        # Always refresh immediately on reveal (don't wait for the first
        # tick) -- e.g. DockManager.show_globals() -- then keep polling
        # while actually visible.
        self.refresh()
        self._timer.start()

    def hideEvent(self, event):
        super().hideEvent(event)
        self._timer.stop()

    def _user_defined_items(self):
        """(name, value) pairs in persistent_env that are the user's own --
        not one of the API functions/values _build_api() re-injects before
        every run (add_block, sim, np, ...) and not the __builtins__
        exec() adds automatically. Calling _build_api() here just to read
        its key set is side-effect-free (it only builds closures, it
        doesn't invoke anything or print) and keeps this filter from
        drifting out of sync with the real API by hand-duplicating its key
        list here."""
        api_keys = set(self.script_manager._build_api(lambda *args: None).keys())
        api_keys.add("__builtins__")
        return [
            (name, value)
            for name, value in self.script_manager.persistent_env.items()
            if name not in api_keys
        ]

    def _rows(self):
        return sorted(self._user_defined_items(), key=lambda item: item[0])

    def refresh(self):
        """Repopulate the table from the live environment -- called on
        open/toggle, after Clear All, and by the auto-refresh timer while
        visible (see _auto_refresh(), which only calls this when the
        snapshot actually changed). No manual Refresh button -- the timer
        is the only trigger while the dock is open. Re-applies the current
        search filter afterward (setRowCount()/setItem() above don't
        preserve per-row hidden state across a full repopulate)."""
        rows = self._rows()

        self.table.setRowCount(len(rows))
        for row, (name, value) in enumerate(rows):
            self.table.setItem(row, 0, QTableWidgetItem(name))
            self.table.setItem(row, 1, QTableWidgetItem(type(value).__name__))
            try:
                value_text = repr(value)
            except Exception as e:
                value_text = f"<unrepr-able: {e}>"
            if len(value_text) > 500:
                value_text = value_text[:500] + "..."
            self.table.setItem(row, 2, QTableWidgetItem(value_text))

        self._last_snapshot = self._snapshot_of(rows)
        self._apply_filter()

    def _on_search_changed(self, text):
        self._search_text = text
        self._apply_filter()

    def _apply_filter(self):
        """Hide rows that don't match self._search_text (against Name or
        Value, case-insensitive) via setRowHidden() -- same approach as
        the Library dock's block search (gui/managers/dock_manager.py),
        rather than rebuilding the table on every keystroke. Also keeps
        count_label showing "N of M" while filtered."""
        text = self._search_text.strip().lower()
        total = self.table.rowCount()
        visible = 0
        for row in range(total):
            if text:
                name_item = self.table.item(row, 0)
                value_item = self.table.item(row, 2)
                name_text = name_item.text().lower() if name_item else ""
                value_text = value_item.text().lower() if value_item else ""
                match = text in name_text or text in value_text
            else:
                match = True
            self.table.setRowHidden(row, not match)
            if match:
                visible += 1

        if text:
            self.count_label.setText(f"{visible} of {total} variable{'s' if total != 1 else ''}")
        else:
            self.count_label.setText(f"{total} variable{'s' if total != 1 else ''}")

    def _snapshot_of(self, rows):
        """A cheap, comparable fingerprint of `rows`' names/values, used by
        _auto_refresh() to skip rebuilding the table (which would otherwise
        reset scroll position/selection every _AUTO_REFRESH_MS even when
        nothing changed). Falls back to a fresh, never-equal-to-anything
        object() (NOT None -- two failures in a row would otherwise compare
        equal and wrongly look "unchanged") if a value's repr() isn't
        reliably callable/comparable -- rare, and just means that tick
        refreshes unconditionally instead of being skipped."""
        try:
            return tuple((name, repr(value)) for name, value in rows)
        except Exception:
            return object()

    def _auto_refresh(self):
        if self._snapshot_of(self._rows()) != self._last_snapshot:
            self.refresh()

    def _on_clear_clicked(self):
        reply = QMessageBox.question(
            self, "Clear Global Variables",
            "Remove every variable a Script or the Console has defined "
            "this session? The built-in API (add_block, sim, np, ...) is "
            "unaffected -- it's always available again on the next run. "
            "This can't be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return
        self.script_manager.clear_globals()
        self.refresh()
