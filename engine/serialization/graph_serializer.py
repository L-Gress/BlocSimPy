"""Graph serialization and deserialization."""
from typing import Dict, List, Any, Tuple
from ..blocks import BLOCK_REGISTRY


class GraphSerializer:
    """Handles serialization and deserialization of block diagrams."""
    
    @staticmethod
    def serialize_graph(blocks_ui: List[Any]) -> Dict[str, Any]:
        """
        Serialize a graph to a dictionary.
        
        Args:
            blocks_ui: List of UIBlock objects
            
        Returns:
            Dictionary representing the graph
        """
        data = {
            "blocks": [],
            "connections": []
        }
        
        # Serialize blocks
        for ui_block in blocks_ui:
            block_data = {
                "class": ui_block.model.__class__.__name__,
                "type": ui_block.model.__class__.__name__,  # Alias for SubGraph compatibility
                "id": ui_block.model.id,
                "position": {"x": ui_block.pos().x(), "y": ui_block.pos().y()},
                "rotation": ui_block.rotation(),
                "params": ui_block.model.params.copy()
            }
            
            # Special handling for SubGraph
            if hasattr(ui_block.model, 'internal_blocks_data'):
                block_data["internal_blocks_data"] = ui_block.model.internal_blocks_data
                block_data["internal_connections_data"] = ui_block.model.internal_connections_data
            
            data["blocks"].append(block_data)
        
        # Serialize connections
        for ui_block in blocks_ui:
            for port_name, port_ui in ui_block.ports_ui.items():
                if not port_ui.is_input:  # Only save from output ports
                    for conn in port_ui.connections:
                        if conn.end_port:
                            conn_data = {
                                "from_block_id": ui_block.model.id,
                                "from_port": port_name,
                                "to_block_id": conn.end_port.model.owner.id,
                                "to_port": conn.end_port.model.name,
                                "points": [[p.x(), p.y()] for p in conn.points]
                            }
                            data["connections"].append(conn_data)
        
        return data
    
    @staticmethod
    def deserialize_graph(data: Dict[str, Any]) -> Tuple[List[Any], List[Dict[str, Any]]]:
        """
        Deserialize a graph from a dictionary.
        
        Args:
            data: Dictionary representing the graph
            
        Returns:
            Tuple of (block_models, connections_data)
        """
        block_models = []
        id_map = {}  # Old ID -> New Block Model
        
        # Recreate blocks
        for block_data in data.get("blocks", []):
            class_name = block_data["class"]
            if class_name in BLOCK_REGISTRY:
                new_block = BLOCK_REGISTRY[class_name]()
                new_block.params = block_data.get("params", {})
                
                # Restore special attributes
                if "internal_blocks_data" in block_data:
                    new_block.internal_blocks_data = block_data["internal_blocks_data"]
                    new_block.internal_connections_data = block_data["internal_connections_data"]
                    # CRITICAL: Sync ports immediately so UIBlock creates them
                    if hasattr(new_block, "refresh_io_ports"):
                        new_block.refresh_io_ports()
                
                # Update label if block has the method
                if hasattr(new_block, "_update_label"):
                    new_block._update_label()
                
                # Store for connection reconstruction
                old_id = block_data["id"]
                id_map[old_id] = new_block
                
                # Store position and rotation for later
                new_block._temp_position = block_data.get("position", {"x": 0, "y": 0})
                new_block._temp_rotation = block_data.get("rotation", 0)
                
                block_models.append(new_block)
        
        # Process connections
        connections_data = []
        for conn_data in data.get("connections", []):
            from_id = conn_data["from_block_id"]
            to_id = conn_data["to_block_id"]
            
            if from_id in id_map and to_id in id_map:
                connections_data.append({
                    "from_block": id_map[from_id],
                    "from_port": conn_data["from_port"],
                    "to_block": id_map[to_id],
                    "to_port": conn_data["to_port"],
                    "points": conn_data.get("points", [])
                })
        
        return block_models, connections_data
