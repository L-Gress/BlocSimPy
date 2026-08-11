"""Owns every top-level QAction (File/Edit/Simulation/Help) and the toolbar.

MainWindow's menu bar reuses these same QAction instances rather than
creating its own -- one shortcut/icon/enabled-state per action, shown in two
places (toolbar + menu) instead of two independent copies that could drift.
"""
from PySide6.QtWidgets import QToolBar, QMessageBox, QProgressDialog
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QThread
from ..dialogs import SimulationSettingsDialog, DiagramCheckDialog, AboutDialog
from ..workers import SimulationWorker
from .. import icon_factory
from engine.simulation import SimulationEngine


class ToolbarManager:
    """Creates the app's QActions, the toolbar that hosts them, and the
    simulation run/cancel flow (including the background thread)."""

    def __init__(self, main_window):
        self.main_window = main_window
        self.sim_duration = 10.0
        self.sim_dt = 0.01
        self.sim_solver = "euler"
        self.toolbar = None
        self.last_result = None  # most recent batch SimulationResult, for the Data Inspector

        # Kept alive while a simulation runs; released once it finishes.
        self._sim_thread = None
        self._sim_worker = None
        self._progress_dialog = None

    def _make_action(self, text, slot, shortcut=None, icon_name=None, parent=None):
        action = QAction(text, parent or self.main_window)
        if icon_name is not None:
            action.setIcon(icon_factory.icon(icon_name))
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

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
            "Save", lambda: mw.scene_manager.save_graph(), QKeySequence.Save, "save"
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
        self.action_run = self._make_action("Run", self.run_simulation, "F5", "run")
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
            "Toggle Library", mw.dock_manager.toggle_library
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

        for action in (self.action_sim_settings, self.action_run, self.action_inspector):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_open_project)
        self.toolbar.addSeparator()
        # action_load ("Open...") is intentionally not on the toolbar --
        # opening a diagram is now naturally reached through User Space
        # (Open Project Folder -> double-click a Diagram), not a generic
        # file-open button. It's still in the File menu for the rare case
        # of opening a diagram from outside the current project folder.
        for action in (self.action_new, self.action_save, self.action_save_as):
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
        for action in (self.action_save_subgraph, self.action_toggle_lib):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_help)

        return self.toolbar

    def set_diagram_actions_enabled(self, enabled):
        """Enable/disable every action that needs an active diagram tab to
        act on. The app can briefly have zero diagram tabs open -- right
        at startup, before New/Open/User-Space creates the first one --
        so these start disabled rather than crashing (or silently doing
        nothing) if clicked in that window. Once any diagram has been
        opened this session, MainWindow's "always keep at least one tab
        open" rule means it never goes back to zero, so this only ever
        runs disabled->enabled in practice."""
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

    def run_simulation(self):
        """Validate the active diagram, then run it on a background thread
        with a cancellable progress dialog so long runs don't freeze the
        UI."""
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

        self.action_run.setEnabled(False)

        self._sim_thread = QThread(self.main_window)
        self._sim_worker = SimulationWorker(engine)
        self._sim_worker.moveToThread(self._sim_thread)

        self._sim_thread.started.connect(self._sim_worker.run)
        self._sim_worker.finished.connect(self._on_simulation_finished)
        self._sim_worker.finished.connect(self._sim_thread.quit)
        self._sim_worker.finished.connect(self._sim_worker.deleteLater)
        self._sim_thread.finished.connect(self._sim_thread.deleteLater)

        self._progress_dialog = QProgressDialog(
            "Running simulation...", "Cancel", 0, 100, self.main_window
        )
        self._progress_dialog.setWindowTitle("Simulation")
        self._progress_dialog.setWindowModality(Qt.WindowModal)
        self._progress_dialog.setMinimumDuration(0)
        self._progress_dialog.setAutoClose(False)
        self._progress_dialog.setAutoReset(False)
        self._progress_dialog.canceled.connect(self._sim_worker.cancel)
        self._sim_worker.progress.connect(lambda frac: self._progress_dialog.setValue(int(frac * 100)))

        self._sim_thread.start()

    def _on_simulation_finished(self, result):
        """Slot for SimulationWorker.finished -- runs on the GUI thread."""
        if self._progress_dialog is not None:
            self._progress_dialog.close()
            self._progress_dialog = None
        self.action_run.setEnabled(True)

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
