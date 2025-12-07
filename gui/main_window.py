import sys
import json
from PySide6.QtWidgets import (QApplication, QMainWindow, QGraphicsView, QDockWidget,
                               QListWidget, QToolBar, QMessageBox, QDialog, QWidget, QVBoxLayout, QLineEdit, QFileDialog, QTabWidget)
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QKeySequence


from PySide6.QtGui import QShortcut

from engine.blocks import BLOCK_REGISTRY, SubGraph
from .scene import NodeScene
from .items import UIBlock, UIConnection
from .dialogs import SimulationSettingsDialog, HelpDialog
from .library import UserLibraryWidget


class GraphicsView(QGraphicsView):
    """Custom QGraphicsView that properly forwards key events to the scene."""
    def keyPressEvent(self, event):
        """Forward key events to the scene."""
        if self.scene():
            self.scene().keyPressEvent(event)
        else:
            super().keyPressEvent(event)


class MainWindow(QMainWindow):
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("BlocSimPy")
        self.resize(1200, 800)

        # --- Scene Setup ---
        self.scene = NodeScene(self)
        self.scene.setSceneRect(0, 0, 5000, 5000)
        self.view = GraphicsView(self.scene)
        self.view.setRenderHint(QPainter.Antialiasing)
        self.view.setFocusPolicy(Qt.StrongFocus)
        self.view.viewport().setFocusPolicy(Qt.StrongFocus)
        self.setCentralWidget(self.view)

        # --- Library Dock Setup ---
        self.dock = QDockWidget("Library", self)
        self.dock_contents = QTabWidget()
        
        # Tab 1: Standard
        self.standard_lib_widget = QWidget()
        sl_layout = QVBoxLayout(self.standard_lib_widget)
        sl_layout.setContentsMargins(0,0,0,0)
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("Search blocks...")
        self.search_bar.textChanged.connect(self.filter_blocks)
        sl_layout.addWidget(self.search_bar)
        self.list_widget = QListWidget()
        self.all_blocks = sorted(BLOCK_REGISTRY.keys())
        for name in self.all_blocks:
            if name not in ["InputPort", "OutputPort"]:
                self.list_widget.addItem(name)
        sl_layout.addWidget(self.list_widget)
        self.list_widget.itemDoubleClicked.connect(self.add_block_to_scene)
        
        # Tab 2: User SubGraphs
        self.user_lib_widget = UserLibraryWidget()
        self.user_lib_widget.load_requested.connect(self.spawn_subgraph_from_library)
        
        self.dock_contents.addTab(self.standard_lib_widget, "Standard")
        self.dock_contents.addTab(self.user_lib_widget, "My SubGraphs")
        self.dock.setWidget(self.dock_contents)
        self.addDockWidget(Qt.LeftDockWidgetArea, self.dock)

        # --- TOOLBAR SETUP ---
        toolbar = QToolBar("Simulation")
        self.addToolBar(toolbar)

        # 1. Main Project Actions (Save/Load Main Graph)
        btn_load = toolbar.addAction("Load Project")
        btn_load.triggered.connect(self.load_graph)

        btn_save = toolbar.addAction("Save Project")
        btn_save.triggered.connect(self.save_graph)

        btn_save_as = toolbar.addAction("Save As...")
        btn_save_as.triggered.connect(self.save_graph_as)

        toolbar.addSeparator()

        # 2. SubGraph Actions
        btn_add_lib = toolbar.addAction("Add Selection to Lib")
        btn_add_lib.triggered.connect(self.save_selected_subgraph_to_library)
        
        btn_up = toolbar.addAction("⬆ Up Level")
        btn_up.triggered.connect(self.go_up_level)

        toolbar.addSeparator()

        # 3. Simulation Actions
        btn_run = toolbar.addAction("Run")
        btn_run.triggered.connect(self.run_simulation)

        btn_help = toolbar.addAction("Help")
        btn_help.triggered.connect(self.show_help)

        # State Variables
        self.blocks_ui = []
        self.current_file = None
        self.navigation_stack = [] # Stack for SubGraph navigation

        # Shortcuts
        self.rotate_shortcut = QShortcut(QKeySequence("R"), self)
        self.rotate_shortcut.activated.connect(self.rotate_selected_blocks)

    def add_block_to_scene(self, list_item):
        type_name = list_item.text()
        if type_name in BLOCK_REGISTRY:
            block_class = BLOCK_REGISTRY[type_name]
            model = block_class()
            ui = UIBlock(model)
            # Add to center of view
            center_pos = self.view.mapToScene(self.view.viewport().rect().center())
            ui.setPos(center_pos)
            self.scene.addItem(ui)
            self.blocks_ui.append(ui)

    # --- NEW METHOD: Save Selection to Library ---
    def save_selected_subgraph_to_library(self):
        """
        Saves the selected SubGraph block to the User Library.
        """
        selected = self.scene.selectedItems()
        # Filter for UIBlocks
        blocks = [i for i in selected if isinstance(i, UIBlock)]
        
        if len(blocks) != 1:
            QMessageBox.warning(self, "Selection Error", "Please select exactly ONE SubGraph block.")
            return
            
        ui_block = blocks[0]
        if not isinstance(ui_block.model, SubGraph):
             QMessageBox.warning(self, "Selection Error", "Selected block is not a SubGraph.")
             return
             
        # Extract Data
        # We need to save: 
        # 1. params (Name, etc)
        # 2. internal_data (The graph inside)
        
        data = {
            "type": "SubGraph",
            "params": ui_block.model.params,
            "internal_data": ui_block.model.internal_data
        }
        
        # Get Current Name for default filename
        default_name = ui_block.model.params.get("BlockName", "SubGraph")
        
        # Delegate saving to the Library Widget
        self.user_lib_widget.save_subgraph(data, default_name)

    # --- NEW METHOD: Spawn from Library ---
    def spawn_subgraph_from_library(self, file_path):
        """
        Loads a JSON file from library and creates a SubGraph block.
        """
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            if data.get("type") != "SubGraph":
                raise ValueError("File is not a valid SubGraph.")
            
            # Create Model
            model = SubGraph()
            model.params = data.get("params", {})
            model.internal_data = data.get("internal_data", {})
            
            # Important: Sync ports immediately so it looks right
            model.sync_ports_from_data()
            model._update_label() # Ensure name is displayed

            # Create UI
            ui = UIBlock(model)
            center_pos = self.view.mapToScene(self.view.viewport().rect().center())
            ui.setPos(center_pos)
            
            self.scene.addItem(ui)
            self.blocks_ui.append(ui)
            
        except Exception as e:
            QMessageBox.critical(self, "Load Error", f"Could not load SubGraph:\n{str(e)}")




    def rotate_selected_blocks(self):
        """Rotate any selected UIBlock items by 90 degrees clockwise."""
        for item in self.scene.selectedItems():
            if isinstance(item, UIBlock):
                item.rotate_90()

    def show_help(self):
        dlg = HelpDialog(self)
        dlg.exec()

    def toggle_library(self):
        """Toggle visibility of the library dock."""
        self.dock.setVisible(not self.dock.isVisible())

    def filter_blocks(self, search_text):
        """Filter blocks in the library list based on search text."""
        self.list_widget.clear()
        search_lower = search_text.lower()
        for block_name in self.all_blocks:
            if search_lower in block_name.lower():
                self.list_widget.addItem(block_name)

    def add_block_to_scene(self, list_item):
        type_name = list_item.text()
        block_class = BLOCK_REGISTRY[type_name]
        model = block_class()
        ui = UIBlock(model)
        ui.setPos(self.view.mapToScene(self.view.viewport().rect().center()))
        self.scene.addItem(ui)
        self.blocks_ui.append(ui)

    def run_simulation(self):
        dialog = SimulationSettingsDialog(self, 10.0, 0.01)
        if dialog.exec() != QDialog.Accepted:
            return
        duration, dt = dialog.get_values()
        if duration is None or dt is None:
            QMessageBox.warning(self, "Invalid Input", "Please enter valid positive numbers for Time and Step.")
            return

        all_models = [b.model for b in self.blocks_ui]
        for m in all_models:
            if hasattr(m, 'reset'): m.reset()
            if hasattr(m, 'initialized'): m.initialized = False

        time_steps = int(duration / dt)
        t = 0.0

        try:
            QApplication.setOverrideCursor(Qt.WaitCursor)
            for _ in range(time_steps):
                for b in all_models:
                    for name, input_port in b.inputs.items():
                        if input_port.connected_port:
                            input_port.value = input_port.connected_port.value

                for b in all_models:
                    b.compute(t, dt)

                for b in all_models:
                    b.update_state(t, dt)

                t += dt

            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Done", f"Simulation Complete.\nDuration: {duration}s\nStep: {dt}s")
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, "Simulation Error", str(e))

    
    
    def get_scene_data(self):
        """Helper: Serializes the current scene to a dictionary."""
        data = {"blocks": [], "connections": []}
        for ui in self.blocks_ui:
            b_data = {
                "id": ui.model.id,
                "type": ui.model.__class__.__name__,
                "x": ui.x(),
                "y": ui.y(),
                "params": ui.model.params.copy() 
            }
            
            # RECURSIVE SAVE: If it's a SubSystem, save its internal_data too
            if isinstance(ui.model, SubGraph):
                # internal_data is already up to date if we haven't entered it,
                # but if we edited it inside, it's stored in the model.
                b_data["internal_data"] = ui.model.internal_data

            data["blocks"].append(b_data)

        for ui in self.blocks_ui:
            for name, port in ui.model.inputs.items():
                if port.connected_port:
                    conn_data = {
                        "from_id": port.connected_port.owner.id,
                        "from_port": port.connected_port.name,
                        "to_id": ui.model.id,
                        "to_port": name
                    }
                    data["connections"].append(conn_data)
        return data

    def load_scene_data(self, data):
        """Helper: Clears scene and loads from dictionary."""
        self.scene.clear()
        self.blocks_ui = []
        id_map = {}

        for b_data in data["blocks"]:
            b_type = b_data["type"]
            if b_type in BLOCK_REGISTRY:
                model = BLOCK_REGISTRY[b_type]()
                model.id = b_data["id"] # Preserve ID
                model.params = b_data["params"]
                
                # RECURSIVE LOAD: If SubSystem, restore internal data
                if isinstance(model, SubGraph) and "internal_data" in b_data:
                    model.internal_data = b_data["internal_data"]
                    # Important: Sync ports so the block looks correct immediately
                    model.sync_ports_from_data()

                ui = UIBlock(model)
                ui.setPos(b_data["x"], b_data["y"])
                self.scene.addItem(ui)
                self.blocks_ui.append(ui)
                id_map[b_data["id"]] = ui

        for c in data["connections"]:
            source_ui = id_map.get(c["from_id"])
            target_ui = id_map.get(c["to_id"])
            if source_ui and target_ui:
                # Be careful with port names, they might have changed if not synced
                if c["from_port"] in source_ui.ports_ui and c["to_port"] in target_ui.ports_ui:
                    out_port_ui = source_ui.ports_ui[c["from_port"]]
                    in_port_ui = target_ui.ports_ui[c["to_port"]]
                    conn = UIConnection(out_port_ui, in_port_ui)
                    self.scene.addItem(conn)
                    self.scene.complete_connection(out_port_ui, in_port_ui, conn)

    # ==========================
    # NAVIGATION LOGIC
    # ==========================

    def enter_subsystem(self, subsystem_ui_block):
        """Called when double-clicking a SubSystem block."""
        
        # 1. Save the current level state
        current_data = self.get_scene_data()
        
        # 2. Store in stack
        # If we are at root, stack is empty.
        # We push: (current_data, subsystem_ui_block_reference)
        self.navigation_stack.append((current_data, subsystem_ui_block))
        
        # 3. Load the subsystem's internal data
        sub_model = subsystem_ui_block.model
        internal_data = sub_model.internal_data
        
        # 4. Clear and Load
        self.load_scene_data(internal_data)
        
        # Update Window Title for feedback
        self.setWindowTitle(f"BlocSimPy - Edit: {sub_model.name}")

    def go_up_level(self):
        """Called by Toolbar button to go back up."""
        if not self.navigation_stack:
            return # Already at root
        
        # 1. Capture the current state (the modified inside of the subgraph)
        child_data = self.get_scene_data()
        
        # 2. Pop the parent state
        # parent_data is the snapshot of the parent graph BEFORE we entered.
        # parent_subsystem_ui is the reference to the block we clicked to enter.
        parent_data, parent_subsystem_ui = self.navigation_stack.pop()
        
        # 3. CRITICAL FIX: Update the parent_data with the new child_data
        # We must find the specific block entry in the parent snapshot and inject the new data.
        target_id = parent_subsystem_ui.model.id
        found = False
        
        for b_dict in parent_data["blocks"]:
            if b_dict["id"] == target_id:
                # Update the internal_data of this block in the snapshot
                b_dict["internal_data"] = child_data
                found = True
                break
        
        if not found:
            print("Warning: Could not link SubGraph data back to parent.")

        # 4. Restore the Parent Scene using the UPDATED snapshot
        # This will recreate the SubGraph block. Because we updated internal_data above,
        # load_scene_data will call sync_ports_from_data(), and the ports will appear correctly.
        self.load_scene_data(parent_data)
        
        # 5. Update Window Title
        if not self.navigation_stack:
            self.setWindowTitle("BlocSimPy")
        else:
            self.setWindowTitle("BlocSimPy - SubGraph")
    
    
    
    def save_graph(self):
        # We must ensure we are at Root before saving to file?
        # Or we can save the current hierarchy state.
        # Ideally, user should be at root, or we need to collapse the stack.
        
        if self.navigation_stack:
            QMessageBox.warning(self, "Save Warning", "Please go up to the Root level before saving to file.")
            return

        # Use generic helper
        data = self.get_scene_data()
        
        if not self.current_file:
            self.save_graph_as()
            return

        try:
            with open(self.current_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=4)
            print(f"Saved to {self.current_file}")
        except Exception as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def load_graph(self):
        if self.navigation_stack:
             QMessageBox.warning(self, "Load Warning", "Please go up to the Root level before loading.")
             return
             
        path, _ = QFileDialog.getOpenFileName(self, "Open Graph", "", "JSON Files (*.json);;All Files (*)")
        if not path: return

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.load_scene_data(data)
            self.current_file = path
        except Exception as e:
            QMessageBox.critical(self, "Load Error", str(e))

    def save_graph_as(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Graph As", "graph.json", "JSON Files (*.json);;All Files (*)")
        if not path:
            return
        # Ensure file has .json extension if user omitted
        if not path.lower().endswith('.json'):
            path = path + '.json'
        self.current_file = path
        return self.save_graph()
