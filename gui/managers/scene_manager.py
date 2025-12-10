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
        
        # Clipboard
        self.clipboard_data = None
        
        # Subsystem navigation
        self.subsystem_stack = []
        self.breadcrumb_label = None
        
    def add_block_to_scene(self, list_item):
        """Add a block from the library to the scene (ListWidget version)."""
        self.add_block_by_name(list_item.text())

    def add_block_by_name(self, block_class_name):
        """Add a block from the library to the scene by string name."""
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
            "connections": subgraph_model.internal_connections_data,
            "params": subgraph_model.params.copy()
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
            
            # Load interface parameters (custom variables & name)
            if "params" in subgraph_data:
                new_subgraph.params.update(subgraph_data["params"])
                # Ensure label updates with loaded name
                if hasattr(new_subgraph, "_update_label"):
                    new_subgraph._update_label()
            
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
        
        # 1. Serialize the CURRENT scene (the inside of the subsystem)
        current_subsystem_data = GraphSerializer.serialize_graph(self.blocks_ui)
        
        # 2. Get the parent context
        parent_context = self.subsystem_stack[-1]
        parent_data = parent_context["data"]
        subsystem_id = parent_context["subsystem_model"].id
        
        # 3. Update the SubGraph block in the PARENT data with new internal data
        # We must find the block data that corresponds to the subsystem we are leaving
        found = False
        for block_data in parent_data.get("blocks", []):
            if block_data.get("id") == subsystem_id:
                block_data["internal_blocks_data"] = current_subsystem_data["blocks"]
                block_data["internal_connections_data"] = current_subsystem_data["connections"]
                found = True
                break
                
        if not found:
            print(f"Warning: Could not find original SubGraph block (ID: {subsystem_id}) in parent data.")

        # 4. Restore parent scene from the UPDATED data
        # This creates NEW block instances, so the old subsystem_model reference is indeed obsolete
        # The GraphSerializer now automatically syncs ports during deserialization (Step 165),
        # so connections are restored correctly by _load_scene_data.
        # We DO NOT need to manually refresh ports here anymore; doing so breaks the just-restored connections.
        self._load_scene_data(parent_data)
        
        self.subsystem_stack.pop()
        self._update_breadcrumb()
        
    def go_to_top_level(self):
        """Navigate back to the top level (First Simulation Layer)."""
        while self.subsystem_stack:
            self.go_up_level()
    
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
    
    def copy_selection(self):
        """Copy selected blocks to clipboard."""
        selected = self.main_window.scene.selectedItems()
        blocks = [item for item in selected if isinstance(item, UIBlock)]
        if not blocks:
            return
            
        self.clipboard_data = GraphSerializer.serialize_graph(blocks)

    def cut_selection(self):
        """Cut selected blocks to clipboard."""
        self.copy_selection()
        
        # Delete selected blocks and connections
        selected = self.main_window.scene.selectedItems()
        # Delete connections first (to avoid issues with block deletion)
        # But scene.delete_block handles connection deletion.
        # Just loop carefully.
        
        # Filter blocks to delete
        blocks_to_delete = [item for item in selected if isinstance(item, UIBlock)]
        # Filter standalone connections (if supported in future, for now just blocks)
        
        scene = self.main_window.scene
        for block in blocks_to_delete:
            scene.delete_block(block)

    def paste_selection(self):
        """Paste blocks from clipboard."""
        if not self.clipboard_data:
            return

        # Deserialize (creates NEW models with FRESH IDs)
        block_models, connections_data = GraphSerializer.deserialize_graph(self.clipboard_data)

        # Map to find UI blocks for connections
        id_to_ui_block = {}
        
        # Determine offset (e.g., center of screen or offset from original)
        # Simple approach: Offset by +20, +20 from original position
        offset_x = 20
        offset_y = 20

        # Create UI Blocks
        selected_items = []
        for block_model in block_models:
            ui_block = UIBlock(block_model)
            
            # Restore position with offset
            if hasattr(block_model, '_temp_position'):
                pos = block_model._temp_position
                new_x = pos['x'] + offset_x
                new_y = pos['y'] + offset_y
                ui_block.setPos(QPointF(new_x, new_y))
                delattr(block_model, '_temp_position')
            
            # Restore rotation
            if hasattr(block_model, '_temp_rotation'):
                ui_block.setRotation(block_model._temp_rotation)
                delattr(block_model, '_temp_rotation')
            
            # Add to Scene
            self.main_window.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            id_to_ui_block[block_model.id] = ui_block
            
            # Select the new items
            ui_block.setSelected(True)
            selected_items.append(ui_block)
            
            # Initialize ports
            if hasattr(block_model, "refresh_io_ports"):
                # Ensure SubGraphs have ports before connecting
                block_model.refresh_io_ports()
                ui_block.refresh_ports()

        # Recreate Connections
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
                    
                    # Offset points if they exist
                    if conn_data.get("points"):
                        conn.points = [QPointF(p[0] + offset_x, p[1] + offset_y) for p in conn_data["points"]]
                    
                    conn.update_path()
                    self.main_window.scene.addItem(conn)
                    from_port_ui.connections.append(conn)
                    to_port_ui.connections.append(conn)
                    to_port_ui.model.connected_port = from_port_ui.model
                    
                    conn.setSelected(True)
        
        # Deselect everything else first?
        # Ideally, we should clear selection before pasting, then select pasted items.
        # But 'set_selected' above only marks them as selected.
        # Let's clear existing selection first.
        # Note: We can't access scene easily inside the loop if we want to clear first.
        # We should have cleared selection at the start of paste.
        pass # Placeholder

    def copy_selection(self):
        """Copy selected blocks to clipboard."""
        selected = self.main_window.scene.selectedItems()
        blocks = [item for item in selected if isinstance(item, UIBlock)]
        if not blocks:
            return
            
        self.clipboard_data = GraphSerializer.serialize_graph(blocks)

    def cut_selection(self):
        """Cut selected blocks to clipboard."""
        self.copy_selection()
        
        # Delete selected blocks (and their connections automatically via scene.delete_block)
        selected = self.main_window.scene.selectedItems()
        blocks_to_delete = [item for item in selected if isinstance(item, UIBlock)]
        
        scene = self.main_window.scene
        for block in blocks_to_delete:
            scene.delete_block(block)

    def paste_selection(self):
        """Paste blocks from clipboard."""
        if not self.clipboard_data:
            return

        # Clear current selection so we can select the pasted items
        self.main_window.scene.clearSelection()

        # Deserialize (creates NEW models with FRESH IDs)
        block_models, connections_data = GraphSerializer.deserialize_graph(self.clipboard_data)

        # Map to find UI blocks for connections
        id_to_ui_block = {}
        
        # Offset by +20, +20 from original position
        offset_x = 20
        offset_y = 20

        # Create UI Blocks
        for block_model in block_models:
            ui_block = UIBlock(block_model)
            
            # Restore position with offset
            if hasattr(block_model, '_temp_position'):
                pos = block_model._temp_position
                new_x = pos['x'] + offset_x
                new_y = pos['y'] + offset_y
                ui_block.setPos(QPointF(new_x, new_y))
                delattr(block_model, '_temp_position')
            
            # Restore rotation
            if hasattr(block_model, '_temp_rotation'):
                ui_block.setRotation(block_model._temp_rotation)
                delattr(block_model, '_temp_rotation')
            
            # Add to Scene
            self.main_window.scene.addItem(ui_block)
            self.blocks_ui.append(ui_block)
            id_to_ui_block[block_model.id] = ui_block
            
            # Initialize ports if SubGraph
            if hasattr(block_model, "refresh_io_ports"):
                 block_model.refresh_io_ports()
                 ui_block.refresh_ports()
            
            # Select the new item
            ui_block.setSelected(True)

        # Recreate Connections
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
                    
                    # Offset points if they exist
                    if conn_data.get("points"):
                        conn.points = [QPointF(p[0] + offset_x, p[1] + offset_y) for p in conn_data["points"]]
                    
                    conn.update_path()
                    self.main_window.scene.addItem(conn)
                    from_port_ui.connections.append(conn)
                    to_port_ui.connections.append(conn)
                    to_port_ui.model.connected_port = from_port_ui.model
                    
                    conn.setSelected(True)

    def _update_breadcrumb(self):
        """Update breadcrumb navigation label."""
        if self.breadcrumb_label:
            depth = len(self.subsystem_stack)
            if depth == 0:
                self.breadcrumb_label.setText("📍 Location: Top Level")
            else:
                self.breadcrumb_label.setText(f"📍 Location: Subsystem (Depth {depth})")
