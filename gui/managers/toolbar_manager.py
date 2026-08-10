"""Manages toolbar creation and toolbar actions."""
from PySide6.QtWidgets import QToolBar, QMessageBox
from PySide6.QtGui import QAction
from ..dialogs import SimulationSettingsDialog, DiagramCheckDialog, DataInspectorDialog
from engine.simulation import SimulationEngine
from engine.serialization import GraphSerializer


class ToolbarManager:
    """Manages the main window toolbar and its actions."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.sim_duration = 10.0
        self.sim_dt = 0.01
        self.sim_solver = "euler"
        self.toolbar = None
        self.last_result = None  # most recent batch SimulationResult, for the Data Inspector
        
    def create_toolbar(self):
        """Create and configure the toolbar."""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        
        # Simulation actions
        action_sim = QAction("⚙ Settings", self.main_window)
        action_sim.triggered.connect(self._show_sim_settings)
        self.toolbar.addAction(action_sim)
        
        action_run = QAction("▶ Run", self.main_window)
        action_run.triggered.connect(self.run_simulation)
        self.toolbar.addAction(action_run)

        action_inspector = QAction("📊 Data Inspector", self.main_window)
        action_inspector.triggered.connect(self.show_data_inspector)
        self.toolbar.addAction(action_inspector)

        self.toolbar.addSeparator()
        
        # File actions
        action_save = QAction("💾 Save", self.main_window)
        action_save.triggered.connect(self.main_window.scene_manager.save_graph)
        self.toolbar.addAction(action_save)
        
        action_load = QAction("📂 Load", self.main_window)
        action_load.triggered.connect(self.main_window.scene_manager.load_graph)
        self.toolbar.addAction(action_load)
        
        action_save_as = QAction("💾 Save As", self.main_window)
        action_save_as.triggered.connect(self.main_window.scene_manager.save_graph_as)
        self.toolbar.addAction(action_save_as)
        
        self.toolbar.addSeparator()
        
        # Subsystem navigation
        action_up = QAction("⬆ Go Up", self.main_window)
        action_up.triggered.connect(self.main_window.scene_manager.go_up_level)
        self.toolbar.addAction(action_up)
        
        self.toolbar.addSeparator()
        
        # Library actions
        action_save_subgraph = QAction("📦 Save SubGraph", self.main_window)
        action_save_subgraph.triggered.connect(self.main_window.scene_manager.save_selected_subgraph_to_library)
        self.toolbar.addAction(action_save_subgraph)
        
        action_toggle_lib = QAction("📚 Toggle Library", self.main_window)
        action_toggle_lib.triggered.connect(self.main_window.dock_manager.toggle_library)
        self.toolbar.addAction(action_toggle_lib)

        # Scripts
        action_scripts = QAction("📜 User Scripts", self.main_window)
        action_scripts.triggered.connect(self.main_window.script_manager.show_editor)
        self.toolbar.addAction(action_scripts)
        
        self.toolbar.addSeparator()
        
        # Help
        action_help = QAction("❓ Help", self.main_window)
        action_help.triggered.connect(self.main_window.show_help)
        self.toolbar.addAction(action_help)
        
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
    
    def run_simulation(self):
        """Run the simulation locally as a fixed-duration batch run."""
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

        # Create simulation engine
        engine = SimulationEngine()

        # Configure engine
        engine.configure(block_models, self.sim_duration, self.sim_dt, solver=self.sim_solver)

        # Validate
        is_valid, error_msg = engine.validate()
        if not is_valid:
            QMessageBox.critical(self.main_window, "Validation Error", error_msg)
            return

        # Run simulation
        result = engine.run()

        if not result.success:
            QMessageBox.critical(self.main_window, "Simulation Error", result.error_message)
            return

        self.last_result = result

        # Display results
        QMessageBox.information(
            self.main_window,
            "Simulation Completed",
            "Simulation finished successfully.\n\n"
            "Double-click any Scope block to view its data, "
            "or use 📊 Data Inspector to see every Scope at once."
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
