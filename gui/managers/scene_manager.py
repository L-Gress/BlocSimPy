"""Manages scene operations, serialization, and subsystem navigation."""
from PySide6.QtWidgets import QMessageBox, QFileDialog
from PySide6.QtCore import QPointF
import json
from engine.serialization import GraphSerializer
from engine.blocks import BLOCK_REGISTRY
from ..items import UIBlock, UIConnection


class SceneManager:
    """Manages all scene-related operations for MainWindow."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.blocks_ui = [] 
        self.current_file_path = None
        
        # Subsystem navigation
        self.subsystem_stack = []
        self.breadcrumb_label = None
        
    def add_block_to_scene(self, list_item):
        """Add a block from the library to the scene."""
        block_class_name = list_item.text()
        if block_class_name in BLOCK_REGISTRY:
            new_block = BLOCK_REGISTRY[block_class_name]()
            ui_block = UIBlock(new_block)
            ui_block.setPos(100, 100)
            self.main_window.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
    
    def save_selected_subgraph_to_library(self):
        """
        Saves the selected SubGraph block to the User Library.
        """
        selected = self.main_window.scene.selectedItems()
        subgraph_blocks = [item for item in selected if isinstance(item, UIBlock) 
                          and item.model.__class__.__name__ == "SubGraph"]
        
        if not subgraph_blocks:
            QMessageBox.information(
                self.main_window,
                "No SubGraph Selected",
                "Please select a SubGraph block to save."
            )
            return
        
        if len(subgraph_blocks) > 1:
            QMessageBox.warning(
                self.main_window,
                "Multiple SubGraphs",
                "Please select only one SubGraph."
            )
            return
        
        subgraph_ui = subgraph_blocks[0]
        subgraph_model = subgraph_ui.model
        
        # Serialize the internal data
        subgraph_data = {
            "blocks": subgraph_model.internal_blocks_data,
            "connections": subgraph_model.internal_connections_data
        }
        
        # Ask for a name
        subgraph_name = subgraph_model.params.get("BlockName", "SubGraph")
        
        # Save via library widget
        self.main_window.user_library_widget.save_subgraph(subgraph_data, subgraph_name)
    
    def spawn_subgraph_from_library(self, file_path):
        """
        Loads a JSON file from library and creates a SubGraph block.
        """
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                subgraph_data = json.load(f)
            
            # Create a new SubGraph block
            if "SubGraph" not in BLOCK_REGISTRY:
                QMessageBox.critical(self.main_window, "Error", "SubGraph block type not found.")
                return
            
            new_subgraph = BLOCK_REGISTRY["SubGraph"]()
            new_subgraph.internal_blocks_data = subgraph_data.get("blocks", [])
            new_subgraph.internal_connections_data = subgraph_data.get("connections", [])
            
            # Refresh ports based on internal InputPort/OutputPort blocks
            new_subgraph.refresh_io_ports()
            
            ui_block = UIBlock(new_subgraph)
            ui_block.setPos(150, 150)
            ui_block.refresh_ports()
            
            self.main_window.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            
            QMessageBox.information(
                self.main_window,
                "SubGraph Loaded",
                f"Loaded SubGraph from {file_path}"
            )
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to load SubGraph: {str(e)}")
    
    def enter_subsystem(self, subsystem_ui_block):
        """Called when double-clicking a SubSystem block."""
        subsystem_model = subsystem_ui_block.model
        
        # Save current scene state
        current_data = GraphSerializer.serialize_graph(self.blocks_ui)
        self.subsystem_stack.append({
            "data": current_data,
            "subsystem_model": subsystem_model
        })
        
        # Load subsystem internal scene
        internal_data = {
            "blocks": subsystem_model.internal_blocks_data,
            "connections": subsystem_model.internal_connections_data
        }
        self._load_scene_data(internal_data)
        self._update_breadcrumb()
    
    def go_up_level(self):
        """Called by Toolbar button to go back up."""
        if not self.subsystem_stack:
            QMessageBox.information(self.main_window, "Top Level", "Already at top level.")
            return
        
        # Save changes to the subsystem
        current_subsystem_data = GraphSerializer.serialize_graph(self.blocks_ui)
        parent_context = self.subsystem_stack[-1]
        parent_context["subsystem_model"].internal_blocks_data = current_subsystem_data["blocks"]
        parent_context["subsystem_model"].internal_connections_data = current_subsystem_data["connections"]
        
        # Refresh I/O ports of the subsystem block based on internal InputPort/OutputPort
        parent_context["subsystem_model"].refresh_io_ports()
        
        # Restore parent scene
        parent_data = parent_context["data"]
        self._load_scene_data(parent_data)
        
        # Update UI for the subsystem block to reflect new ports
        for ui_block in self.blocks_ui:
            if ui_block.model == parent_context["subsystem_model"]:
                ui_block.refresh_ports()
                break
        
        self.subsystem_stack.pop()
        self._update_breadcrumb()
    
    def save_graph(self):
        """Save the current graph."""
        if self.current_file_path:
            self._save_to_file(self.current_file_path)
        else:
            self.save_graph_as()
    
    def load_graph(self):
        """Load a graph from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self.main_window,
            "Load Graph",
            "",
            "JSON Files (*.json)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                self._load_scene_data(data)
                self.current_file_path = file_path
                QMessageBox.information(self.main_window, "Success", f"Loaded from {file_path}")
            except Exception as e:
                QMessageBox.critical(self.main_window, "Error", f"Failed to load: {str(e)}")
    
    def save_graph_as(self):
        """Save the current graph to a new file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self.main_window,
            "Save Graph As",
            "",
            "JSON Files (*.json)"
        )
        if file_path:
            self._save_to_file(file_path)
            self.current_file_path = file_path
    
    def _save_to_file(self, file_path):
        """Internal method to save graph to file."""
        try:
            data = GraphSerializer.serialize_graph(self.blocks_ui)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
            QMessageBox.information(self.main_window, "Success", f"Saved to {file_path}")
        except Exception as e:
            QMessageBox.critical(self.main_window, "Error", f"Failed to save: {str(e)}")
    
    def _load_scene_data(self, data):
        """Helper: Clears scene and loads from dictionary."""
        # Clear current scene
        self.main_window.scene.clear()
        self.blocks_ui.clear()
        
        # Deserialize
        block_models, connections_data = GraphSerializer.deserialize_graph(data)
        
        # Create UI blocks
        id_to_ui_block = {}
        for block_model in block_models:
            ui_block = UIBlock(block_model)
            
            # Restore position and rotation
            if hasattr(block_model, '_temp_position'):
                pos = block_model._temp_position
                ui_block.setPos(QPointF(pos['x'], pos['y']))
                delattr(block_model, '_temp_position')
            
            if hasattr(block_model, '_temp_rotation'):
                ui_block.setRotation(block_model._temp_rotation)
                delattr(block_model, '_temp_rotation')
            
            self.main_window.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            id_to_ui_block[block_model.id] = ui_block
        
        # Recreate connections
        for conn_data in connections_data:
            from_block = conn_data["from_block"]
            to_block = conn_data["to_block"]
            from_port_name = conn_data["from_port"]
            to_port_name = conn_data["to_port"]
            
            from_ui = id_to_ui_block.get(from_block.id)
            to_ui = id_to_ui_block.get(to_block.id)
            
            if from_ui and to_ui:
                from_port_ui = from_ui.ports_ui.get(from_port_name)
                to_port_ui = to_ui.ports_ui.get(to_port_name)
                
                if from_port_ui and to_port_ui:
                    conn = UIConnection(from_port_ui, to_port_ui)
                    
                    # Restore path points if available
                    if conn_data.get("points"):
                        conn.points = [QPointF(p[0], p[1]) for p in conn_data["points"]]
                    
                    conn.update_path()
                    self.main_window.scene.addItem(conn)
                    from_port_ui.connections.append(conn)
                    to_port_ui.connections.append(conn)
                    to_port_ui.model.connected_port = from_port_ui.model
    
    def _update_breadcrumb(self):
        """Update breadcrumb navigation label."""
        if self.breadcrumb_label:
            depth = len(self.subsystem_stack)
            if depth == 0:
                self.breadcrumb_label.setText("📍 Location: Top Level")
            else:
                self.breadcrumb_label.setText(f"📍 Location: Subsystem (Depth {depth})")
