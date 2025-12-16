from ..models import BlockModel
import threading
import queue
import time
from typing import Dict, Any, List

class SubGraph(BlockModel):
    """
    A container block that holds an internal graph.
    Can run synchronously (Standard) or asynchronously (Threaded/Audio) in its own thread.
    """
    
    BLOCK_INFO = {
        "description": "Container block with custom interface/variables",
        "parameters": "BlockName, Execution Mode, Sample Rate",
        "formula": "Executes internal diagram with variable substitution ($VarName)",
        "usage": "Double-click to enter. Ctrl+Double-click to edit variables. Execution Mode: Standard (Sync), Threaded (Async), Audio (Async Realtime)",
        "category": "Structure"
    }
    
    def __init__(self):
        super().__init__("SubGraph")
        self.is_container = True
        
        # Internal structure data
        self.internal_blocks_data = []
        self.internal_connections_data = []
        self.execution_blocks = []
        self.execution_map = {}
        
        # Threading / Execution State
        self.thread = None
        self.running = False
        self.processor = None
        self.input_queues: Dict[str, queue.Queue] = {}
        self.output_queues: Dict[str, queue.Queue] = {}
        self.last_output_values: Dict[str, float] = {}

        # Parameters
        self.add_param("BlockName", "MySubGraph")
        self.add_param("Execution Mode", "Standard") # Options: Standard, Threaded, Audio
        self.add_param("Sample Rate", 100.0)         # Only for Threaded/Audio modes
        
        self._update_label()

    def _update_label(self):
        """Formats the name to show Type on top, Name below, and Mode if not Standard."""
        user_name = self.params.get("BlockName", "MySubGraph")
        mode = self.params.get("Execution Mode", "Standard")
        
        label = f"SubGraph\n({user_name})"
        if mode != "Standard":
            label += f"\n[{mode}]"
        self.name = label

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    def __setstate__(self, state):
        self.__dict__.update(state)
        # Re-init runtime transients that aren't pickled or need reset
        self.thread = None
        self.running = False
        self.processor = None
        self.input_queues = {}
        self.output_queues = {}
        self.last_output_values = {}
        self._update_label()

    # --- Port Management ---
    def sync_ports_from_data(self):
        """Reads internal_blocks_data to determine external inputs/outputs."""
        self.inputs.clear()
        self.outputs.clear()
        
        in_ports_data = sorted(
            [b for b in self.internal_blocks_data if b["type"] == "InputPort"],
            key=lambda x: x["params"].get("PortName", "")
        )
        out_ports_data = sorted(
            [b for b in self.internal_blocks_data if b["type"] == "OutputPort"],
            key=lambda x: x["params"].get("PortName", "")
        )

        for b_data in in_ports_data:
            name = b_data["params"].get("PortName", "In")
            self.add_input(name)
            
        for b_data in out_ports_data:
            name = b_data["params"].get("PortName", "Out")
            self.add_output(name)
    
    def refresh_io_ports(self):
        self.sync_ports_from_data()

    # --- Execution Logic ---

    def reset(self):
        """Prepare internal blocks and execution state."""
        self.cleanup() # Stop any existing threads
        self._instantiate_internal_blocks()
        
        mode = self.params.get("Execution Mode", "Standard")
        
        if mode == "Standard":
            # Standard: Direct Execution (No Queues)
            pass
            
        elif mode in ["Threaded", "Audio"]:
            # Async: Setup Queues and Processor
            self._setup_async_execution(mode)

    def _instantiate_internal_blocks(self):
        """Standard instantiation logic (copied from original reset)."""
        from . import BLOCK_REGISTRY
        self.execution_blocks = []
        self.execution_map = {}
        
        # 1. Ensure Variable Defaults
        for b_data in self.internal_blocks_data:
            for p_val in b_data.get("params", {}).values():
                if isinstance(p_val, str) and p_val.strip().startswith("$"):
                    var_name = p_val.strip()[1:]
                    if var_name and var_name not in self.params:
                        self.params[var_name] = 0.0

        # 2. Instantiate
        for b_data in self.internal_blocks_data:
            b_type = b_data["type"]
            if b_type in BLOCK_REGISTRY:
                instance = BLOCK_REGISTRY[b_type]()
                instance.params = b_data["params"].copy()
                
                # Variable Substitution
                for p_key, p_val in instance.params.items():
                    if isinstance(p_val, str) and p_val.strip().startswith("$"):
                        var_name = p_val.strip()[1:]
                        if var_name in self.params:
                            instance.params[p_key] = self.params[var_name]
                
                if hasattr(instance, "reset"):
                    instance.reset()
                
                # Tags
                if b_type == "InputPort": instance.is_subsystem_input = True
                if b_type == "OutputPort": instance.is_subsystem_output = True
                
                self.execution_blocks.append(instance)
                self.execution_map[b_data["id"]] = instance

        # 3. Connections
        for c_data in self.internal_connections_data:
            source = self.execution_map.get(c_data["from_block_id"])
            target = self.execution_map.get(c_data["to_block_id"])
            if source and target:
                out_p = source.outputs.get(c_data["from_port"])
                in_p = target.inputs.get(c_data["to_port"])
                if out_p and in_p:
                    in_p.connected_port = out_p

    def _setup_async_execution(self, mode):
        """Initialize queues and start the worker thread."""
        from server.processors import TimerProcessor, AudioProcessor
        
        # 1. Create Queues 
        # Size=1 means we only keep the LATEST value (Drop Oldest)
        self.input_queues = {name: queue.Queue(maxsize=1) for name in self.inputs}
        self.output_queues = {name: queue.Queue(maxsize=1) for name in self.outputs}
        self.last_output_values = {name: 0.0 for name in self.outputs}
        
        rate = float(self.params.get("Sample Rate", 100.0))
        
        # 2. Create Processor
        if mode == "Audio":
            # 44100Hz default for Audio
            self.processor = AudioProcessor(self.execution_blocks, sample_rate=rate)
        else:
            # Threaded (Timer based)
            self.processor = TimerProcessor(self.execution_blocks, rate=rate, steps_per_batch=1)
            
        # 3. Hook Processor IO to Queues
        # We need to monkey-patch or wrap the processor's input/output logic?
        # Better: The processor runs `compute()` on blocks. We just need to make sure
        # the InputPort blocks inside read from our queues, and OutputPort blocks write to our queues.
        
        # We can achieve this by overriding the `compute` or `value` property of the Input/Output Ports inside?
        # OR: We create a "Pre-Step" and "Post-Step" hook in the processor?
        # The simplest way without changing Processor architecture significantly is to 
        # let the InputPort/OutputPort blocks themselves handle the queue interaction if they detect they are inside a threaded subgraph.
        # BUT: The blocks don't know they are inside a threaded subgraph easily.
        
        # Solution: We assign a `read_from_queue` and `write_to_queue` function to the specific instances 
        # of InputPort and OutputPort found in `self.execution_blocks`.
        
        for b in self.execution_blocks:
            if getattr(b, 'is_subsystem_input', False):
                p_name = b.params.get("PortName")
                if p_name in self.input_queues:
                    # Monkey-patch compute to read from queue
                    q = self.input_queues[p_name]
                    # Define closure
                    def pull_from_queue(block=b, q=q):
                        try:
                            # Non-blocking get. If empty, keep last value (state) or 0.
                            val = q.get_nowait()
                            block.outputs["out"].value = val
                            block._last_val = val
                        except queue.Empty:
                            # No new data, hold last value
                            if not hasattr(block, '_last_val'): block._last_val = 0.0
                            block.outputs["out"].value = block._last_val
                    
                    # Bind it to a method name we can call manually or via a wrapper
                    b.custom_compute = pull_from_queue

            if getattr(b, 'is_subsystem_output', False):
                p_name = b.params.get("PortName")
                if p_name in self.output_queues:
                    q = self.output_queues[p_name]
                    def push_to_queue(block=b, q=q):
                         val = block.inputs["in"].value
                         # Put latest, overwrite if full (Drop Oldest)
                         try:
                             q.put_nowait(val)
                         except queue.Full:
                             try:
                                 q.get_nowait() # Pop old
                                 q.put_nowait(val) # Push new
                             except:
                                 pass
                    b.custom_compute_post = push_to_queue

        # 4. Wrap the processor's step function or block list to call these hooks?
        # The `AudioProcessor` and `TimerProcessor` iterate `sorted_blocks` and call `compute`.
        # We can just wrap the `compute` method of these specific Port instances!
        
        for b in self.execution_blocks:
            if hasattr(b, 'custom_compute'):
                # Input Port: Read Queue -> Set Output
                # original compute does nothing usually for Ports, or just passthrough
                b.compute = lambda t, dt, f=b.custom_compute: f()
            
            if hasattr(b, 'custom_compute_post'):
                 # Output Port: Read Input -> Write Queue
                 # We need this to happen AFTER the value connects. 
                 # Since it's topologically sorted, OutputPorts are last. 
                 # So we can just put the logic in `compute`.
                 b.compute = lambda t, dt, f=b.custom_compute_post: f()

        # 5. Start Processor
        if hasattr(self.processor, "start"):
            self.processor.start() # Starts the thread
        elif hasattr(self.processor, "callback"):
            # AudioProcessor is passive (callback based). 
            # We need to start the Stream.
            import sounddevice as sd
            # We need to store the stream to stop it later
            # Ensure rate is int for PortAudio
            int_rate = int(rate)
            self.stream = sd.Stream(channels=2, callback=self.processor.callback, samplerate=int_rate)
            self.stream.start()

        self.running = True

    def compute(self, t, dt):
        """
        Main execution Step.
        """
        mode = self.params.get("Execution Mode", "Standard")
        
        if mode == "Standard":
            self._compute_standard(t, dt)
        else:
            self._compute_async(t, dt)

    def _compute_standard(self, t, dt):
        if not self.execution_blocks: return

        # 1. Bridge External Inputs -> Internal InputPorts
        for b in self.execution_blocks:
            if getattr(b, 'is_subsystem_input', False):
                p_name = b.params.get("PortName")
                if p_name in self.inputs:
                    b.outputs["out"].value = self.inputs[p_name].value

        # 2. Run Internal Blocks
        for b in self.execution_blocks:
            # Transfer data internally
            for name, port in b.inputs.items():
                if port.connected_port:
                    port.value = port.connected_port.value
            b.compute(t, dt)
            if hasattr(b, 'update_state'):
                b.update_state(t, dt)

        # 3. Bridge Internal OutputPorts -> External Outputs
        for b in self.execution_blocks:
            if getattr(b, 'is_subsystem_output', False):
                p_name = b.params.get("PortName")
                if p_name in self.outputs:
                        self.outputs[p_name].value = b.inputs["in"].value

    def _compute_async(self, t, dt):
        """
        Async Bridge:
        Main Thread Pushes Inputs -> Queue -> Worker Thread
        Worker Thread Pushes Outputs -> Queue -> Main Thread
        """
        # 1. Push Inputs to Queues
        for name, port in self.inputs.items():
            if name in self.input_queues:
                q = self.input_queues[name]
                val = port.value
                try:
                    q.put_nowait(val)
                except queue.Full:
                    # Drop oldest to keep latency low
                    try:
                        q.get_nowait()
                        q.put_nowait(val)
                    except:
                        pass
        
        # 2. Pop Outputs from Queues
        for name, port in self.outputs.items():
            if name in self.output_queues:
                q = self.output_queues[name]
                try:
                    val = q.get_nowait()
                    self.last_output_values[name] = val
                    port.value = val
                except queue.Empty:
                    # Keep holding last value (Zero-Order Hold)
                    port.value = self.last_output_values.get(name, 0.0)

    def cleanup(self):
        """Stop threads and streams."""
        if hasattr(self, 'processor') and self.processor:
            if hasattr(self.processor, 'stop'):
                self.processor.stop()
        
        if hasattr(self, 'stream') and self.stream:
            self.stream.stop()
            self.stream.close()
            self.stream = None
            
        self.running = False

    def __del__(self):
        self.cleanup()

    def get_editor_dialog(self, parent=None):
        """Custom dialog to edit SubGraph parameters and variables."""
        from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, 
                                       QTableWidget, QTableWidgetItem, 
                                       QPushButton, QLabel, QLineEdit, QComboBox,
                                       QDialogButtonBox, QHeaderView, QWidget, QMessageBox)
        from PySide6.QtCore import Qt

        dialog = QDialog(parent)
        dialog.setWindowTitle("SubGraph Interface Editor")
        dialog.resize(500, 500)
        
        layout = QVBoxLayout(dialog)

        # --- Section 1: General Settings ---
        form_layout = QVBoxLayout()
        
        # Name
        name_layout = QHBoxLayout()
        name_layout.addWidget(QLabel("Block Name:"))
        name_edit = QLineEdit(self.params.get("BlockName", "MySubGraph"))
        name_layout.addWidget(name_edit)
        form_layout.addLayout(name_layout)
        
        # Mode
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Execution Mode:"))
        mode_combo = QComboBox()
        mode_combo.addItems(["Standard", "Threaded", "Audio"])
        current_mode = self.params.get("Execution Mode", "Standard")
        mode_combo.setCurrentText(current_mode)
        mode_layout.addWidget(mode_combo)
        form_layout.addLayout(mode_layout)

        # Sample Rate
        sr_layout = QHBoxLayout()
        sr_layout.addWidget(QLabel("Sample Rate (Hz):"))
        sr_edit = QLineEdit(str(self.params.get("Sample Rate", 100.0)))
        sr_layout.addWidget(sr_edit)
        form_layout.addLayout(sr_layout)
        
        layout.addLayout(form_layout)
        
        # --- Section 2: Variables ---
        layout.addWidget(QLabel("<b>Custom Variables:</b>"))
        layout.addWidget(QLabel("Define variables here. Use them inside as <i>$VariableName</i>."))
        
        table = QTableWidget()
        table.setColumnCount(2)
        table.setHorizontalHeaderLabels(["Name", "Value"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(table)
        
        def add_row(key="", val=""):
            row = table.rowCount()
            table.insertRow(row)
            table.setItem(row, 0, QTableWidgetItem(str(key)))
            table.setItem(row, 1, QTableWidgetItem(str(val)))
            
        # Populate
        reserved = ["BlockName", "Execution Mode", "Sample Rate"]
        for k, v in self.params.items():
            if k in reserved: continue
            add_row(k, v)
        
        # --- Buttons ---
        btn_layout = QHBoxLayout()
        btn_add = QPushButton("Add Variable")
        btn_remove = QPushButton("Remove Selected")
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        layout.addLayout(btn_layout)
        
        def on_add():
            add_row("NewVar", "0.0")
            
        def on_remove():
            rows = sorted(set(index.row() for index in table.selectedIndexes()), reverse=True)
            for r in rows:
                table.removeRow(r)
                
        btn_add.clicked.connect(on_add)
        btn_remove.clicked.connect(on_remove)
        
        # --- Dialog Buttons ---
        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(dialog.accept)
        btns.rejected.connect(dialog.reject)
        layout.addWidget(btns)
        
        original_accept = dialog.accept
        
        def save_and_accept():
            # 1. Validate
            new_params = {}
            new_params["BlockName"] = name_edit.text().strip()
            new_params["Execution Mode"] = mode_combo.currentText()
            try:
                new_params["Sample Rate"] = float(sr_edit.text())
            except:
                new_params["Sample Rate"] = 100.0
            
            for i in range(table.rowCount()):
                key_item = table.item(i, 0)
                val_item = table.item(i, 1)
                
                if key_item and val_item:
                    key = key_item.text().strip()
                    val_str = val_item.text().strip()
                    
                    if not key: continue
                    if key in reserved:
                        QMessageBox.warning(dialog, "Invalid Name", f"'{key}' is reserved.")
                        return

                    # Try float conversion
                    try:
                        val = float(val_str)
                    except ValueError:
                        val = val_str
                    new_params[key] = val
            
            self.params = new_params
            if hasattr(self, "_update_label"):
                self._update_label()
                
            original_accept()

        dialog.accept = save_and_accept
        
        return dialog