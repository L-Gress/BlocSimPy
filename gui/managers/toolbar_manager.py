"""Manages toolbar creation and toolbar actions."""
from PySide6.QtWidgets import QToolBar, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from ..dialogs import SimulationSettingsDialog
from engine.simulation import SimulationEngine


class ToolbarManager:
    """Manages the main window toolbar and its actions."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.sim_duration = 10.0
        self.sim_dt = 0.01
        self.toolbar = None
        
    def create_toolbar(self):
        """Create and configure the toolbar."""
        self.toolbar = QToolBar("Main Toolbar")
        self.toolbar.setMovable(False)
        
        # Simulation actions
        action_sim = QAction("⚙ Simulation Settings", self.main_window)
        action_sim.triggered.connect(self._show_sim_settings)
        self.toolbar.addAction(action_sim)
        
        action_run = QAction("▶ Run", self.main_window)
        action_run.triggered.connect(self.run_simulation)
        self.toolbar.addAction(action_run)
        
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
            current_dt=self.sim_dt
        )
        if dialog.exec():
            duration, dt = dialog.get_values()
            if duration and dt:
                self.sim_duration = duration
                self.sim_dt = dt
    
    def run_simulation(self):
        """Run the simulation using the SimulationEngine."""
        if not self.main_window.scene_manager.blocks_ui:
            QMessageBox.warning(self.main_window, "No Blocks", "Add blocks to the scene first.")
            return
        
        # Create simulation engine
        engine = SimulationEngine()
        
        # Collect all block models
        block_models = [ui_block.model for ui_block in self.main_window.scene_manager.blocks_ui]
        
        # Configure engine
        engine.configure(block_models, self.sim_duration, self.sim_dt)
        
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
        
        # Display results
        QMessageBox.information(
            self.main_window,
            "Simulation Completed",
            "Simulation finished successfully.\n\n"
            "Double-click any Scope block to view its data."
        )
