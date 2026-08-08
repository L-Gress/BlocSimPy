"""Manages toolbar creation and toolbar actions."""
from PySide6.QtWidgets import (
    QToolBar, QMessageBox, QDialog, QVBoxLayout, QLabel, QPushButton
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from ..dialogs import SimulationSettingsDialog
from engine.simulation import SimulationEngine
from engine.serialization import GraphSerializer


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
        """Run the simulation locally.

        Graphs containing Audio I/O blocks run live against the sound
        hardware (hardware-clocked, until stopped); all other graphs run
        as a fixed-duration batch simulation.
        """
        if not self.main_window.scene_manager.blocks_ui:
            QMessageBox.warning(self.main_window, "No Blocks", "Add blocks to the scene first.")
            return

        # Collect all block models
        block_models = [ui_block.model for ui_block in self.main_window.scene_manager.blocks_ui]

        has_audio_io = any(b.__class__.__name__ in ["AudioInput", "AudioOutput"] for b in block_models)
        if has_audio_io:
            self._run_audio_realtime(block_models)
            return

        # Create simulation engine
        engine = SimulationEngine()

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

    def _run_audio_realtime(self, block_models):
        """Stream an audio-driven graph against the sound hardware until the user stops it."""
        import sounddevice as sd
        from engine.simulation.processors import AudioProcessor

        for block in block_models:
            if hasattr(block, "reset"):
                block.reset()

        sample_rate = 44100
        buffer_size = 1024

        # Device selection: honor per-block "Device" params if the user picked one.
        in_device = None
        out_device = None
        for block in block_models:
            dev = block.params.get("Device")
            if not dev or dev == "default":
                continue
            try:
                val = int(dev)
            except (TypeError, ValueError):
                val = dev
            if block.__class__.__name__ == "AudioInput":
                in_device = val
            elif block.__class__.__name__ == "AudioOutput":
                out_device = val

        processor = AudioProcessor(block_models, sample_rate)

        try:
            stream = sd.Stream(channels=2, samplerate=sample_rate, blocksize=buffer_size,
                                callback=processor.callback, device=(in_device, out_device),
                                latency='low')
            stream.start()
        except Exception as e:
            QMessageBox.critical(self.main_window, "Audio Error", f"Could not start audio stream: {e}")
            return

        dialog = QDialog(self.main_window)
        dialog.setWindowTitle("Running (Audio)")
        layout = QVBoxLayout(dialog)
        layout.addWidget(QLabel("Audio simulation is running live.\nClose this window to stop."))
        btn_stop = QPushButton("⏹ Stop")
        btn_stop.clicked.connect(dialog.accept)
        layout.addWidget(btn_stop)

        try:
            dialog.exec()
        finally:
            stream.stop()
            stream.close()
