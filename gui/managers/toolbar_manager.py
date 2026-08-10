"""Owns every top-level QAction (File/Edit/Simulation/Help) and the toolbar.

MainWindow's menu bar reuses these same QAction instances rather than
creating its own -- one shortcut/icon/enabled-state per action, shown in two
places (toolbar + menu) instead of two independent copies that could drift.
"""
from PySide6.QtWidgets import QToolBar, QMessageBox, QProgressDialog, QStyle
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtCore import Qt, QThread
from ..dialogs import SimulationSettingsDialog, DiagramCheckDialog, DataInspectorDialog, AboutDialog
from ..workers import SimulationWorker
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

    def _icon(self, standard_pixmap):
        return self.main_window.style().standardIcon(standard_pixmap)

    def _make_action(self, text, slot, shortcut=None, icon=None, parent=None):
        action = QAction(text, parent or self.main_window)
        if icon is not None:
            action.setIcon(self._icon(icon))
        if shortcut is not None:
            action.setShortcut(shortcut)
        action.triggered.connect(slot)
        return action

    def create_toolbar(self):
        """Create every QAction, wire it up, and lay them out on the toolbar."""
        style = QStyle
        sm = self.main_window.scene_manager

        # --- File ---
        self.action_new = self._make_action("New", sm.new_graph, QKeySequence.New, style.SP_FileIcon)
        self.action_load = self._make_action("Open...", sm.load_graph, QKeySequence.Open, style.SP_DialogOpenButton)
        self.action_save = self._make_action("Save", sm.save_graph, QKeySequence.Save, style.SP_DialogSaveButton)
        self.action_save_as = self._make_action(
            "Save As...", sm.save_graph_as, QKeySequence.SaveAs, style.SP_DialogSaveButton
        )
        self.action_quit = self._make_action(
            "Exit", self.main_window.close, QKeySequence.Quit, style.SP_DialogCloseButton
        )

        # --- Edit ---
        self.action_undo = self._make_action(
            "Undo", sm.undo_manager.undo, QKeySequence.Undo, style.SP_ArrowBack
        )
        self.action_redo = self._make_action("Redo", sm.undo_manager.redo, None, style.SP_ArrowForward)
        self.action_redo.setShortcuts([QKeySequence.Redo, QKeySequence("Ctrl+Y")])
        self.action_cut = self._make_action("Cut", sm.cut_selection, QKeySequence.Cut)
        self.action_copy = self._make_action("Copy", sm.copy_selection, QKeySequence.Copy)
        self.action_paste = self._make_action("Paste", sm.paste_selection, QKeySequence.Paste)
        self.action_select_all = self._make_action(
            "Select All", lambda: self.main_window.scene.select_all(), QKeySequence.SelectAll
        )
        self.action_delete = self._make_action(
            "Delete", lambda: self.main_window.scene.delete_selected(), QKeySequence.Delete
        )

        # --- Simulation ---
        self.action_sim_settings = self._make_action(
            "Settings...", self._show_sim_settings, None, style.SP_FileDialogDetailedView
        )
        self.action_run = self._make_action("Run", self.run_simulation, "F5", style.SP_MediaPlay)
        self.action_inspector = self._make_action(
            "Data Inspector", self.show_data_inspector, None, style.SP_FileDialogContentsView
        )

        # --- Subsystem navigation ---
        self.action_up = self._make_action("Go Up", sm.go_up_level, None, style.SP_ArrowUp)

        # --- Library ---
        self.action_save_subgraph = self._make_action(
            "Save SubGraph", sm.save_selected_subgraph_to_library, None, style.SP_DirIcon
        )
        self.action_toggle_lib = self._make_action(
            "Toggle Library", self.main_window.dock_manager.toggle_library
        )
        self.action_scripts = self._make_action(
            "User Scripts", self.main_window.script_manager.show_editor, None, style.SP_FileDialogListView
        )

        # --- Help ---
        self.action_help = self._make_action(
            "Help", self.main_window.show_help, QKeySequence.HelpContents, style.SP_DialogHelpButton
        )
        self.action_about = self._make_action(
            "About BlocSimPy", self.show_about, None, style.SP_MessageBoxInformation
        )

        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)

        for action in (self.action_sim_settings, self.action_run, self.action_inspector):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        for action in (self.action_new, self.action_save, self.action_load, self.action_save_as):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_undo)
        self.toolbar.addAction(self.action_redo)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_up)
        self.toolbar.addSeparator()
        for action in (self.action_save_subgraph, self.action_toggle_lib, self.action_scripts):
            self.toolbar.addAction(action)
        self.toolbar.addSeparator()
        self.toolbar.addAction(self.action_help)

        return self.toolbar

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
        """Validate the diagram, then run it on a background thread with a
        cancellable progress dialog so long runs don't freeze the UI."""
        if not self.main_window.scene_manager.blocks_ui:
            QMessageBox.warning(self.main_window, "No Blocks", "Add blocks to the scene first.")
            return

        # Collect all block models
        block_models = [ui_block.model for ui_block in self.main_window.scene_manager.blocks_ui]

        # "Update Diagram" pre-flight check: catch algebraic loops and
        # unconnected inputs before running, rather than failing mid-run
        # (or, for unconnected inputs, silently reading 0.0 unnoticed).
        check_engine = SimulationEngine()
        check_engine.blocks = block_models
        issues = check_engine.check_diagram()
        if issues:
            check_dialog = DiagramCheckDialog(issues, self.main_window)
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
            self.main_window.statusBar().showMessage("Simulation cancelled.", 5000)
            return

        if not result.success:
            QMessageBox.critical(self.main_window, "Simulation Error", result.error_message)
            return

        self.last_result = result

        QMessageBox.information(
            self.main_window,
            "Simulation Completed",
            "Simulation finished successfully.\n\n"
            "Double-click any Scope block to view its data, "
            "or use Data Inspector to see every Scope at once."
        )

    def show_data_inspector(self):
        """Open the Data Inspector for the most recent batch run's Scope data."""
        if self.last_result is None or not self.last_result.scope_data:
            QMessageBox.information(
                self.main_window, "No Data",
                "Run a simulation first to have data to inspect."
            )
            return
        DataInspectorDialog(self.last_result, self.main_window).exec()
