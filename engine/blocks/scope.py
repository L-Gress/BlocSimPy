"""
Enhanced Scope Block with Multiple Inputs, Zoom/Pan, and Configuration Dialog.
All scope-related features are contained in this single file.
"""

from ..models import BlockModel
import csv
import numpy as np
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QGroupBox, QTabWidget, QWidget, QCheckBox, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt


class ScopeDialog(QDialog):
    """
    Unified Scope dialog for both configuration and data viewing.
    Embedded within scope.py for self-contained functionality.
    """
    
    def __init__(self, scope_block, parent=None):
        super().__init__(parent)
        self.scope_block = scope_block
        self.setWindowTitle(f"Scope: {scope_block.params.get('BlockName', 'Scope')}")
        self.resize(1000, 650)
        self._setup_ui()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Tab widget for organized sections
        tabs = QTabWidget()
        
        # --- Configuration Tab ---
        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        
        input_group = QGroupBox("Input Ports Configuration")
        input_group_layout = QVBoxLayout()
        
        # Current status
        status_label = QLabel(f"📊 Current inputs: {self.scope_block.num_inputs}")
        status_label.setStyleSheet("font-weight: bold; color: #2E86AB;")
        input_group_layout.addWidget(status_label)
        
        # Number of inputs control
        controls_layout = QHBoxLayout()
        controls_layout.addWidget(QLabel("Number of input ports:"))
        
        self.num_inputs_spin = QSpinBox()
        self.num_inputs_spin.setMinimum(1)
        self.num_inputs_spin.setMaximum(20)
        self.num_inputs_spin.setValue(self.scope_block.num_inputs)
        self.num_inputs_spin.setToolTip("Set how many signals to monitor (1-20)")
        controls_layout.addWidget(self.num_inputs_spin)
        controls_layout.addStretch()
        
        input_group_layout.addLayout(controls_layout)
        
        # Apply button for configuration
        apply_config_btn = QPushButton("✓ Apply Configuration")
        apply_config_btn.setStyleSheet("background-color: #2E86AB; color: white; font-weight: bold; padding: 8px 15px;")
        apply_config_btn.clicked.connect(self._apply_config)
        input_group_layout.addWidget(apply_config_btn)
        
        # Help text
        help_text = QLabel(
            "ℹ️ Info:\n"
            "• Each input will be plotted with a different color\n"
            "• Input ports are named: in1, in2, in3, ...\n"
            "• After simulation, switch to 'Data Viewer' tab to see results"
        )
        help_text.setWordWrap(True)
        help_text.setStyleSheet("color: #666; font-size: 9pt; padding: 10px; background: #f0f0f0; border-radius: 5px;")
        input_group_layout.addWidget(help_text)
        
        input_group.setLayout(input_group_layout)
        config_layout.addWidget(input_group)
        config_layout.addStretch()
        
        tabs.addTab(config_tab, "⚙️ Configuration")
        
        # --- Data Viewer Tab ---
        viewer_tab = QWidget()
        viewer_layout = QVBoxLayout(viewer_tab)

        # Get data from scope
        time_array, data_dict = self.scope_block.get_data_arrays()

        from gui.widgets import SignalPlotWidget
        plot = SignalPlotWidget(title="Scope Output", parent=viewer_tab)
        plot.set_series({name: (time_array, arr) for name, arr in data_dict.items()})
        viewer_layout.addWidget(plot)

        export_btn = QPushButton("⬇ Export CSV")
        export_btn.clicked.connect(self._export_csv)
        export_row = QHBoxLayout()
        export_row.addWidget(export_btn)
        export_row.addStretch()
        viewer_layout.addLayout(export_row)

        tabs.addTab(viewer_tab, "📊 Data Viewer")
        
        # Add tabs to main layout
        layout.addWidget(tabs)
        
        # Bottom buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        close_btn = QPushButton("✓ Close")
        close_btn.setStyleSheet("padding: 5px 20px;")
        close_btn.clicked.connect(self.accept)
        button_layout.addWidget(close_btn)
        
        layout.addLayout(button_layout)
    
    def _export_csv(self):
        """Export recorded data as CSV via export_csv_rows() (pure/Qt-free, see Scope)."""
        rows = self.scope_block.export_csv_rows()
        if len(rows) <= 1:
            QMessageBox.information(self, "No Data", "Run the simulation first to have data to export.")
            return

        file_path, _ = QFileDialog.getSaveFileName(self, "Export Scope Data", "", "CSV Files (*.csv)")
        if not file_path:
            return

        try:
            with open(file_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerows(rows)
            QMessageBox.information(self, "Export Complete", f"Saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", str(e))

    def _apply_config(self):
        """Apply configuration changes to the scope block."""
        new_num_inputs = self.num_inputs_spin.value()
        self.scope_block.params["NumInputs"] = new_num_inputs
        self.scope_block.refresh_io_ports()
        self.scope_block.needs_port_refresh = True

        # Show confirmation
        from PySide6.QtWidgets import QMessageBox
        QMessageBox.information(self, "Configuration Applied", 
                               f"Scope configured with {new_num_inputs} input(s).\n\n"
                               "The block ports have been updated.")


class Scope(BlockModel):
    """
    Enhanced Scope Block with Multiple Inputs and Interactive Visualization.
    
    Features:
    - Multiple input ports (configurable 1-20)
    - Interactive zoom and pan
    - Data export capabilities
    - Real-time signal monitoring
    """
    
    BLOCK_INFO = {
        "description": "Records and displays signal data over time with interactive viewer",
        "parameters": "Number of inputs (1-20)",
        "formula": "Records all input signals during simulation",
        "usage": "Visualize signals, debug systems, analyze results. Double-click after simulation to view data",
        "category": "Sinks"
    }
    
    def __init__(self):
        super().__init__("Scope")

        # NumInputs lives in params (not just the num_inputs mirror below)
        # so it actually round-trips through GraphSerializer -- a Scope
        # configured with >1 input used to silently lose its extra ports
        # and their connections on save/reload, since num_inputs was never
        # part of params.
        self.add_param("NumInputs", 1)
        self.num_inputs = 1
        self.add_input("in1")

        # Data storage - using both naming conventions for compatibility
        self.time_data = []      # Required by engine (SimulationEngine)
        self.value_data = []     # Required by engine (primary input)
        self.input_data = {}     # Dict: input_name -> [values]

        # Flag to trigger UI port refresh
        self.needs_port_refresh = False

    def refresh_io_ports(self):
        """Rebuild in1..inN from params['NumInputs']. Called by
        GraphSerializer/scene_manager after load/paste, and by the config
        dialog on Apply -- the single source of truth for this block's
        port count is params['NumInputs']; num_inputs is a convenience
        mirror kept in sync here."""
        target = max(1, min(20, int(self.params.get("NumInputs", self.num_inputs))))
        current = self.num_inputs

        if target > current:
            for i in range(current + 1, target + 1):
                self.add_input(f"in{i}")
        elif target < current:
            for i in range(target + 1, current + 1):
                input_name = f"in{i}"
                if input_name in self.inputs:
                    del self.inputs[input_name]
                if input_name in self.input_data:
                    del self.input_data[input_name]

        self.num_inputs = target
        self.params["NumInputs"] = target

    def compute(self, t, dt, context=None):
        """Store data from all input ports at each time step."""
        # Store time (only once per timestep)
        if not self.time_data or self.time_data[-1] != t:
            self.time_data.append(t)
        
        # Store data from each input
        for input_name, input_port in self.inputs.items():
            if input_name not in self.input_data:
                self.input_data[input_name] = []
            
            val = input_port.value if input_port.value is not None else 0.0
            self.input_data[input_name].append(val)
            
            # Store primary input for engine compatibility
            if input_name == "in1":
                self.value_data.append(val)
    
    def reset(self):
        """Clear all stored data."""
        self.time_data = []
        self.value_data = []
        self.input_data = {}
    
    def get_data_arrays(self):
        """
        Get data as numpy arrays for plotting.
        
        Returns:
            tuple: (time_array, dict of {input_name: data_array})
        """
        time_array = np.array(self.time_data) if self.time_data else np.array([])
        data_dict = {}
        
        for input_name, values in self.input_data.items():
            data_dict[input_name] = np.array(values) if values else np.array([])
        
        return time_array, data_dict

    def export_csv_rows(self):
        """Build CSV rows (header + data, one row per timestep) from recorded
        data: [time, in1, in2, ...]. Pure/Qt-free (mirrors get_data_arrays())
        so it's directly unit-testable without a QApplication; the dialog's
        Export CSV button just writes these rows with the stdlib csv module.
        """
        time_array, data_dict = self.get_data_arrays()
        names = list(data_dict.keys())

        rows = [["time"] + names]
        for i, t in enumerate(time_array):
            row = [t]
            for name in names:
                arr = data_dict[name]
                row.append(arr[i] if i < len(arr) else "")
            rows.append(row)
        return rows

    def get_editor_dialog(self, parent=None):
        """
        Return unified Scope dialog for both configuration and data viewing.
        This is the single access point for the Scope block.
        """
        return ScopeDialog(self, parent)
