"""Owns every top-level QAction (File/Edit/Simulation/Help) and the toolbar.

MainWindow's menu bar reuses these same QAction instances rather than
creating its own -- one shortcut/icon/enabled-state per action, shown in two
places (toolbar + menu) instead of two independent copies that could drift.
"""
import os
from PySide6.QtWidgets import QToolBar, QMessageBox, QProgressBar, QApplication
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QThread
from ..dialogs import SimulationSettingsDialog, DiagramCheckDialog, AboutDialog
from ..workers import SimulationWorker
from .. import icon_factory
from engine.simulation import SimulationEngine


class ToolbarManager:
    """Creates the app's QActions, the toolbar that hosts them, and the
    Run/Stop flow -- one toggle button shared by diagram simulation
    (background QThread, see run_simulation()) and Script execution
    (run_script(), cooperative on the GUI thread -- see its own docstring
    for why it isn't threaded the same way)."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.sim_duration = 10.0
        self.sim_dt = 0.01
        self.sim_solver = "euler"
        self.toolbar = None
        self.run_progress = None
        self.last_result = None  # most recent batch SimulationResult, for the Data Inspector

        # Kept alive while a simulation runs; released once it finishes.
        self._sim_thread = None
        self._sim_worker = None

        # None while idle; "sim" or "script" while the Run button is
        # showing its Stop state (see _set_running()/_set_idle()).
        self._run_kind = None
        self._script_cancel_requested = False
        self._running_script_path = None

        # (action, icon_name) for every action built with an icon --
        # refresh_icons() re-fetches icon_factory.icon(icon_name) for each
        # one after a theme switch (see gui/managers/theme_manager.py),
        # since icon_factory doesn't cache/re-theme pixmaps already handed
        # to a QAction on its own.
        self._icon_actions = []

    def _make_action(self, text, slot, shortcut=None, icon_name=None, parent=None):
        action = QAction(text, parent or self.main_window)
        if icon_name is not None:
            action.setIcon(icon_factory.icon(icon_name))
            self._icon_actions.append((action, icon_name))
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

    def refresh_icons(self):
        """Re-draw every toolbar/menu action's icon in the current theme
        (see gui/icon_factory.py's set_theme()) -- called after the app-wide
        theme switches. action_run is a special case: it isn't in
        _icon_actions' fixed name because it toggles between "run"/"stop"
        icons at runtime (see _set_running()/_set_idle())."""
        for action, icon_name in self._icon_actions:
            action.setIcon(icon_factory.icon(icon_name))
        self.action_run.setIcon(icon_factory.icon("stop" if self._run_kind is not None else "run"))

    def create_toolbar(self):
        """Create every QAction, wire it up, and lay them out on the
        toolbar. Every action that acts on a diagram is wired via a lambda
        that reads `self.main_window.scene_manager` fresh at click time --
        it's a property pointing at whichever diagram tab is currently
        active (see MainWindow), so binding directly to e.g.
        `main_window.scene_manager.save_graph` here would permanently
        capture whichever diagram happened to be active when the toolbar
        was built (there being none yet, in fact -- this runs before the
        first diagram tab exists)."""
        mw = self.main_window

        # --- File ---
        self.action_open_project = self._make_action(
            "Open Project Folder...", mw.project_manager.open_project_dialog,
            None, "project"
        )
        self.action_new = self._make_action(
            "New", lambda: mw.open_diagram_tab(), QKeySequence.New, "new"
        )
        self.action_load = self._make_action(
            "Open...", lambda: mw.open_diagram_dialog(), QKeySequence.Open, "open"
        )
        self.action_save = self._make_action(
            "Save", self._on_save_clicked, QKeySequence.Save, "save"
        )
        self.action_save_as = self._make_action(
            "Save As...", lambda: mw.scene_manager.save_graph_as(), QKeySequence.SaveAs, "save_as"
        )
        self.action_quit = self._make_action(
            "Exit", mw.close, QKeySequence.Quit, "quit"
        )

        # --- Edit ---
        self.action_undo = self._make_action(
            "Undo", lambda: mw.scene_manager.undo_manager.undo(), QKeySequence.Undo, "undo"
        )
        self.action_redo = self._make_action(
            "Redo", lambda: mw.scene_manager.undo_manager.redo(), None, "redo"
        )
        self.action_redo.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Y")])
        self.action_cut = self._make_action(
            "Cut", lambda: mw.scene_manager.cut_selection(), QKeySequence.Cut, "cut"
        )
        self.action_copy = self._make_action(
            "Copy", lambda: mw.scene_manager.copy_selection(), QKeySequence.Copy, "copy"
        )
        self.action_paste = self._make_action(
            "Paste", lambda: mw.scene_manager.paste_selection(), QKeySequence.Paste, "paste"
        )
        self.action_select_all = self._make_action(
            "Select All", lambda: mw.scene.select_all(), QKeySequence.SelectAll, "select_all"
        )
        self.action_delete = self._make_action(
            "Delete", lambda: mw.scene.delete_selected(), QKeySequence.Delete, "delete"
        )
        self.action_duplicate = self._make_action(
            "Duplicate", lambda: mw.scene_manager.duplicate_selection(), QKeySequence("Ctrl+D"), "duplicate"
        )
        self.action_rename = self._make_action(
            "Rename", lambda: mw.scene_manager.rename_selected(), QKeySequence("F2"), "rename"
        )

        # --- View / Zoom ---
        self.action_zoom_in = self._make_action(
            "Zoom In", lambda: mw.view.zoom_in(), QKeySequence("Ctrl+="), "zoom_in"
        )
        self.action_zoom_out = self._make_action(
            "Zoom Out", lambda: mw.view.zoom_out(), QKeySequence("Ctrl+-"), "zoom_out"
        )
        self.action_zoom_fit = self._make_action(
            "Zoom to Fit", lambda: mw.view.zoom_to_fit(), QKeySequence("Ctrl+0"), "zoom_fit"
        )

        # --- Simulation ---
        self.action_sim_settings = self._make_action(
            "Settings...", self._show_sim_settings, None, "settings"
        )
        self.action_run = self._make_action("Run", self._on_run_or_stop_clicked, "F5", "run")
        self.action_inspector = self._make_action(
            "Data Inspector", self.show_data_inspector, None, "inspector"
        )

        # --- Subsystem navigation ---
        self.action_up = self._make_action(
            "Go Up", lambda: mw.scene_manager.go_up_level(), None, "up"
        )

        # --- Library ---
        self.action_save_subgraph = self._make_action(
            "Save SubGraph", lambda: mw.scene_manager.save_selected_subgraph_to_library(), None, "subgraph"
        )
        self.action_toggle_lib = self._make_action(
            "Toggle Library", mw.dock_manager.toggle_library, None, "library"
        )
        self.action_toggle_console = self._make_action(
            "Toggle Console", mw.dock_manager.toggle_console, QKeySequence("Ctrl+`"), "console"
        )
        self.action_toggle_globals = self._make_action(
            "Toggle Global Variables", mw.dock_manager.toggle_globals, QKeySequence("Ctrl+Shift+G"), "globals"
        )
        self.action_clear_globals = self._make_action(
            "Clear Global Variables...", self.clear_globals, None, "clear_globals"
        )
        self.action_toggle_theme = self._make_action(
            "Toggle Dark Mode", mw.theme_manager.toggle, QKeySequence("Ctrl+Shift+D"), "theme"
        )

        # --- Help ---
        self.action_help = self._make_action(
            "Help", self.main_window.show_help, QKeySequence.HelpContents, "help"
        )
        self.action_about = self._make_action(
            "About BlocSimPy", self.show_about, None, "about"
        )

        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setObjectName("main_toolbar")  # required by QMainWindow.saveState()/restoreState()
        self.toolbar.setMovable(False)

        self.toolbar.addAction(self.action_sim_settings)
        self.toolbar.addAction(self.action_run)

        # Inline progress -- replaces the old modal QProgressDialog popup.
        # Hidden while idle; shown next to Run (now showing its Stop icon)
        # for the duration of a simulation or Script run -- real 0-100%
        # for a simulation (SimulationWorker.progress), indeterminate/busy
        # for a Script (no fine-grained progress available for arbitrary
        # Python, only for whatever sim() call it might make -- see
        # run_script()).
        self.run_progress = QProgressBar()
        self.run_progress.setRange(0, 100)
        self.run_progress.setValue(0)
        self.run_progress.setTextVisible(False)
        self.run_progress.setMinimumWidth(80)
        self.run_progress.setMaximumWidth(120)
        self.run_progress.setVisible(False)
        self.toolbar.addWidget(self.run_progress)

        self.toolbar.addAction(self.action_inspector)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_open_project)
        self.toolbar.addSeparator()
        # action_load ("Open...") is intentionally not on the toolbar --
        # opening a diagram is now naturally reached through User Space
        # (Open Project Folder -> double-click a Diagram), not a generic
        # file-open button. It's still in the File menu for the rare case
        # of opening a diagram from outside the current project folder.
        for action in (self.action_new, self.action_save, self.action_save_as, self.action_save_subgraph):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_undo)
        self.toolbar.addAction(self.action_redo)
        self.toolbar.addSeparator()
        for action in (self.action_zoom_out, self.action_zoom_in, self.action_zoom_fit):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_up)
        self.toolbar.addSeparator()
        for action in (self.action_toggle_lib, self.action_toggle_console, self.action_toggle_globals):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_toggle_theme)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_help)

        return self.toolbar

    def set_diagram_actions_enabled(self, enabled):
        """Enable/disable every action that needs an active diagram tab to
        act on. The app can have zero diagram tabs open -- at startup,
        before New/Open/User-Space creates the first one, or any time
        after: closing the last one just leaves the workspace empty rather
        than reopening a blank diagram you didn't ask for. Called with
        False in that case, so these don't crash (or silently do nothing)
        if clicked.

        action_run/action_save are ALSO in this list but are a special
        case: they're just as usable with a Script tab focused and no
        diagram open at all (see MainWindow.active_script_widget()/
        _update_run_save_enabled()), which calls this with False then
        immediately re-enables just those two if a Script is still open --
        so don't assume "disabled" here means neither is clickable."""
        for action in (
            self.action_save, self.action_save_as,
            self.action_undo, self.action_redo,
            self.action_cut, self.action_copy, self.action_paste,
            self.action_select_all, self.action_delete,
            self.action_duplicate, self.action_rename,
            self.action_zoom_in, self.action_zoom_out, self.action_zoom_fit,
            self.action_up, self.action_save_subgraph, self.action_run,
        ):
            action.setEnabled(enabled)

    def _show_sim_settings(self):
        """Show simulation settings dialog."""
        dialog = SimulationSettingsDialog(
            self.main_window,
            current_duration=self.sim_duration,
            current_dt=self.sim_dt,
            current_solver=self.sim_solver
        )
        if dialog.exec():
            duration, dt = dialog.get_values()
            if duration and dt:
                self.sim_duration = duration
                self.sim_dt = dt
                self.sim_solver = dialog.get_solver()

    def show_about(self):
        AboutDialog(self.main_window).exec()

    def clear_globals(self):
        """Clear Global Variables (View menu / Global Variables dock):
        wipe every variable a Script run or the Console has
        defined this session (see ScriptManager.clear_globals()) -- after
        confirming, since unlike most editing actions on the canvas this
        has no Undo. The built-in API (add_block, sim, np, ...) is
        unaffected."""
        reply = QMessageBox.question(
            self.main_window, "Clear Global Variables",
            "Remove every variable a Script or the Console has defined "
            "this session? The built-in API (add_block, sim, np, ...) is "
            "unaffected -- it's always available again on the next run. "
            "This can't be undone.",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        self.main_window.script_manager.clear_globals()

        dm = self.main_window.dock_manager
        if dm.globals_widget is not None:
            dm.globals_widget.refresh()
        if dm.console_widget is not None:
            dm.console_widget.log_external(
                "Clear Global Variables",
                "✓ Cleared all global variables.",
            )
        self._status("Cleared all global variables.")

    def _on_run_or_stop_clicked(self):
        """Slot for action_run -- a toggle, not a fixed "run" button (see
        _set_running()/_set_idle()). While idle, dispatches to whichever
        makes sense for the currently-focused central-area tab: a Script
        tab runs that Script (run_script()); anything else (a Diagram,
        Simulation results, or nothing) runs the active diagram
        (run_simulation()) same as always. While something is already
        running, this same click instead stops it (_stop_current_run())
        -- the icon/tooltip already say "Stop" by then, see _set_running()."""
        if self._run_kind is not None:
            self._stop_current_run()
            return

        mw = self.main_window
        script_widget = mw.active_script_widget() if hasattr(mw, "active_script_widget") else None
        if script_widget is not None:
            self.run_script(script_widget)
        else:
            self.run_simulation()

    def _on_save_clicked(self):
        """Slot for action_save -- Ctrl+S saves whichever kind of tab is
        focused: a Script tab saves itself (ScriptEditorWidget.save_script(),
        the same method its own confirm-discard-on-close prompt already
        used), anything else saves the active diagram, same as always."""
        mw = self.main_window
        script_widget = mw.active_script_widget() if hasattr(mw, "active_script_widget") else None
        if script_widget is not None:
            script_widget.save_script()
        else:
            mw.scene_manager.save_graph()

    def _set_running(self, kind):
        """Flip Run into its Stop state (icon/text) and reveal the inline
        progress indicator -- kind is "sim" (real 0-100% progress, driven
        by SimulationWorker.progress -- see run_simulation()) or "script"
        (no fine-grained progress for arbitrary Python, so the bar just
        runs indeterminate/busy -- see run_script())."""
        self._run_kind = kind
        self.action_run.setIcon(icon_factory.icon("stop"))
        self.action_run.setText("Stop")
        self.run_progress.setVisible(True)
        if kind == "script":
            self.run_progress.setRange(0, 0)  # indeterminate/busy
        else:
            self.run_progress.setRange(0, 100)
            self.run_progress.setValue(0)

    def _set_idle(self):
        self._run_kind = None
        self.action_run.setIcon(icon_factory.icon("run"))
        self.action_run.setText("Run")
        self.run_progress.setVisible(False)

    def _stop_current_run(self):
        """Cancel whatever's currently running -- a simulation cancels
        cleanly at its next progress checkpoint (SimulationEngine.run()
        already polls for this every step loop, same as before this
        toggle existed). A Script can only be interrupted if it happens to
        be inside a sim() call right now (same should_cancel, threaded
        through -- see run_script()); arbitrary Python in between has no
        safe way to interrupt mid-statement, so Stop just requests it and
        it takes effect at the next sim() checkpoint or when the script
        naturally finishes, whichever comes first."""
        if self._run_kind == "sim" and self._sim_worker is not None:
            self._sim_worker.cancel()
        elif self._run_kind == "script":
            self._script_cancel_requested = True
            self._status("Stopping... (takes effect at the script's next sim() call, or when it finishes)")

    def _on_run_progress(self, fraction):
        self.run_progress.setValue(int(fraction * 100))

    def run_simulation(self):
        """Validate the active diagram, then run it on a background
        thread (see the Run/Stop toggle -- _on_run_or_stop_clicked())."""
        if hasattr(self.main_window, "show_diagram_editor"):
            self.main_window.show_diagram_editor()

        sm = self.main_window.scene_manager
        if sm is None or not sm.blocks_ui:
            self._status("Add blocks to the scene first.")
            return

        # Collect all block models
        block_models = [ui_block.model for ui_block in sm.blocks_ui]

        # "Update Diagram" pre-flight check: catch algebraic loops and
        # unconnected inputs before running, rather than failing mid-run
        # (or, for unconnected inputs, silently reading 0.0 unnoticed).
        check_engine = SimulationEngine()
        check_engine.blocks = block_models
        issues = check_engine.check_diagram_detailed()
        if issues:
            check_dialog = DiagramCheckDialog(issues, self.main_window, main_window=self.main_window)
            if not check_dialog.exec():
                return

        # Create and configure the simulation engine
        engine = SimulationEngine()
        engine.configure(block_models, self.sim_duration, self.sim_dt, solver=self.sim_solver)

        is_valid, error_msg = engine.validate()
        if not is_valid:
            QMessageBox.critical(self.main_window, "Validation Error", error_msg)
            return

        self._sim_thread = QThread(self.main_window)
        self._sim_worker = SimulationWorker(engine)
        self._sim_worker.moveToThread(self._sim_thread)

        self._sim_thread.started.connect(self._sim_worker.run)
        self._sim_worker.finished.connect(self._on_simulation_finished)
        self._sim_worker.finished.connect(self._sim_thread.quit)
        self._sim_worker.finished.connect(self._sim_worker.deleteLater)
        self._sim_thread.finished.connect(self._sim_thread.deleteLater)
        self._sim_worker.progress.connect(self._on_run_progress)

        self._set_running("sim")
        self._sim_thread.start()

    def _on_simulation_finished(self, result):
        """Slot for SimulationWorker.finished -- runs on the GUI thread."""
        self._set_idle()

        if result.cancelled:
            self._status("Simulation cancelled.")
            return

        if not result.success:
            QMessageBox.critical(self.main_window, "Simulation Error", result.error_message)
            return

        self.last_result = result

        # A fresh tab per run (not a replacing dialog), so re-running with
        # different parameters lets you flip between this and earlier
        # runs' results instead of only ever seeing the latest.
        if hasattr(self.main_window, "open_simulation_tab"):
            self.main_window.open_simulation_tab(result)
        self._status("Simulation finished.")

    def run_script(self, script_widget):
        """Run a Script tab's content via the same Run/Stop toggle a
        diagram simulation uses (see _on_run_or_stop_clicked()) -- output
        goes to the Console dock (revealed if hidden), same as before this
        was unified with the diagram's own Run button.

        Deliberately NOT a background QThread like run_simulation(): the
        scripting API (add_block, set_param, ...) directly manipulates
        QGraphicsScene/UIBlock objects, which are only safe to touch from
        the GUI thread -- moving execute_script() itself off it would make
        most of the API unsafe to call from a running Script. Instead this
        stays on the GUI thread but cooperatively pumps the Qt event loop
        (QApplication.processEvents()) at the same cadence
        SimulationEngine.run() already reports progress/polls for
        cancellation at, via any sim() call the script makes -- see
        ScriptManager.execute_script()'s should_cancel/on_progress. That
        keeps the window repainting and responsive, and lets Stop actually
        interrupt a long sim() call, without the much larger risk of
        threading the whole scripting API. A script with no sim() call in
        a tight Python loop still simply runs to completion before control
        returns -- there's no safe way to interrupt arbitrary Python
        mid-statement without real OS threads."""
        self._script_cancel_requested = False
        self._running_script_path = script_widget.file_path

        dock_manager = getattr(self.main_window, "dock_manager", None)
        console_widget = getattr(dock_manager, "console_widget", None)
        if console_widget is not None:
            if hasattr(dock_manager, "show_console"):
                dock_manager.show_console()
            if hasattr(console_widget, "set_input_enabled"):
                console_widget.set_input_enabled(False)

        self._set_running("script")
        # Paint the Stop icon/progress bar now, before the blocking call
        # below -- otherwise they wouldn't appear until the script (or its
        # first sim() checkpoint) hands control back.
        QApplication.processEvents()

        def _pump_and_check_cancel():
            QApplication.processEvents()
            return self._script_cancel_requested

        script_content = script_widget.editor.toPlainText()
        result_text = self.main_window.script_manager.execute_script(
            script_content,
            should_cancel=_pump_and_check_cancel,
            on_progress=self._on_run_progress,
        )

        self._set_idle()
        if console_widget is not None:
            if hasattr(console_widget, "set_input_enabled"):
                console_widget.set_input_enabled(True)
            console_widget.log_external(f"Run Script: {os.path.basename(self._running_script_path)}", result_text)
        self._running_script_path = None
        self._status("Script finished.")

    def show_data_inspector(self):
        """Bring the most recent run's results tab to front (Simulation
        menu / toolbar), reopening it if it was closed."""
        if self.last_result is None or not self.last_result.scope_data:
            self._status("Run a simulation first to have data to inspect.")
            return
        if hasattr(self.main_window, "focus_or_open_simulation_tab"):
            self.main_window.focus_or_open_simulation_tab(self.last_result)

    def _status(self, message):
        """Routine, non-blocking confirmation shown in the status bar
        instead of an interrupting QMessageBox.information() -- see
        MainWindow.show_status()."""
        if hasattr(self.main_window, "show_status"):
            self.main_window.show_status(message)
