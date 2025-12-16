"""Manages toolbar creation and toolbar actions."""
from PySide6.QtWidgets import QToolBar, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from ..dialogs import SimulationSettingsDialog, DeployDialog, DeploymentManagerDialog
from engine.simulation import SimulationEngine
from engine.serialization import GraphSerializer
import urllib.request
import json


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
        action_sim = QAction("⚙ Settings", self.main_window)
        action_sim.triggered.connect(self._show_sim_settings)
        self.toolbar.addAction(action_sim)
        
        action_run = QAction("▶ Run", self.main_window)
        action_run.triggered.connect(self.run_simulation)
        self.toolbar.addAction(action_run)
        
        action_deploy = QAction("🚀 Deploy", self.main_window)
        action_deploy.triggered.connect(self.deploy_simulation)
        self.toolbar.addAction(action_deploy)

        action_manage = QAction("📡 Manage", self.main_window)
        action_manage.triggered.connect(self.show_deployment_manager)
        self.toolbar.addAction(action_manage)
        
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
        """Run the simulation locally."""
        if not self.main_window.scene_manager.blocks_ui:
            QMessageBox.warning(self.main_window, "No Blocks", "Add blocks to the scene first.")
            return

        # Check for Audio Blocks
        for ui_block in self.main_window.scene_manager.blocks_ui:
            name = ui_block.model.__class__.__name__
            if name in ["AudioInput", "AudioOutput"]:
                QMessageBox.critical(
                    self.main_window, 
                    "Simulation Error", 
                    "Cannot Run local simulation with Audio blocks.\n"
                    "Please use 'Deploy' instead."
                )
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

    def deploy_simulation(self):
        """Deploy the current graph to the Realtime Server."""
        # 1. Check blocks exist
        if not self.main_window.scene_manager.blocks_ui:
            return

        # 2. Check for InputPorts (Must be absent)
        has_inputs = False
        for ui_block in self.main_window.scene_manager.blocks_ui:
            if ui_block.model.__class__.__name__ == "InputPort":
                has_inputs = True
                break
        
        if has_inputs:
            QMessageBox.warning(
                self.main_window, 
                "Deploy Error", 
                "Cannot deploy a SubGraph that has Input Ports.\n"
                "The deployed graph must be self-contained or use Audio Inputs."
            )
            return
            
        # 3. Determine Configuration from Context
        # Default settings
        settings = {
            "execution_mode": "Auto Detect", 
            "sample_rate": 44100,
            "buffer_size": 1024
        }
        
        # Override if inside a SubGraph
        if self.main_window.scene_manager.subsystem_stack:
            context = self.main_window.scene_manager.subsystem_stack[-1]
            container = context.get("subsystem_model")
            if container:
                # Map Subgraph params to Server config
                mode = container.params.get("Execution Mode", "Standard")
                settings["execution_mode"] = mode
                
                try:
                    rate = float(container.params.get("Sample Rate", 44100.0))
                    settings["sample_rate"] = rate
                except:
                    pass
        
        # 4. Serialize Graph
        graph_data = GraphSerializer.serialize_graph(self.main_window.scene_manager.blocks_ui)
        
        payload = {
            "graph": graph_data,
            "config": settings
        }
        
        default_url = "http://localhost:8080"
        
        # Deploy Helper
        def try_deploy(url, key=None):
            req_url = url + "/deploy"
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(req_url, data=data, headers={'Content-Type': 'application/json'})
            if key: req.add_header('X-API-Key', key)
            with urllib.request.urlopen(req) as f:
                return f.read().decode('utf-8')

        # 5. Attempt Quick Deploy (Localhost)
        failed_quick = False
        try:
            resp = try_deploy(default_url)
            QMessageBox.information(self.main_window, "Deploy Success", f"Server responded: {resp}")
        except:
            failed_quick = True
            
        # 6. Fallback to Dialog if quick deploy failed or user wants to change server
        if failed_quick:
            # We don't ask to configure params anymore, just server details
            dialog = DeployDialog(self.main_window, default_url=default_url)
            if dialog.exec():
                conn_settings = dialog.get_settings()
                # conn_settings only has 'url' and 'api_key' now
                
                try:
                    resp = try_deploy(conn_settings["url"], conn_settings.get("api_key"))
                    QMessageBox.information(self.main_window, "Deploy Success", f"Server responded: {resp}")
                except Exception as e2:
                    QMessageBox.critical(self.main_window, "Deploy Failed", str(e2))

    def show_deployment_manager(self):
        """Show the deployment manager dialog."""
        dialog = DeploymentManagerDialog(self.main_window)
        dialog.exec()
