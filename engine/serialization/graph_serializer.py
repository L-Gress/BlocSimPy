"""Graph serialization and deserialization."""
from typing import Dict, List, Any, Tuple
from ..blocks import BLOCK_REGISTRY


class GraphSerializer:
    """Handles serialization and deserialization of block diagrams."""
    
    @staticmethod
    def serialize_graph(blocks_ui: List[Any], annotations_ui: List[Any] = None,
                         sim_params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Serialize a graph to a dictionary.

        Args:
            blocks_ui: List of UIBlock objects
            annotations_ui: Optional list of UIAnnotation objects (free-text
                canvas notes, not attached to any block). Omitted/None
                produces no "annotations" key, so old save files and any
                caller not touching annotations are unaffected.
            sim_params: Optional dict of simulation settings (duration, dt,
                solver -- see ToolbarManager). Omitted/None produces no
                "simulation" key, same backward-compatibility rationale as
                annotations_ui above.

        Returns:
            Dictionary representing the graph
        """
        data = {
            "blocks": [],
            "connections": []
        }

        if annotations_ui:
            data["annotations"] = [
                {"text": a.toPlainText(), "x": a.pos().x(), "y": a.pos().y()}
                for a in annotations_ui
            ]

        if sim_params:
            data["simulation"] = dict(sim_params)
        
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

                # Sync ports immediately so UIBlock creates them correctly.
                # This covers SubGraph (whose ports derive from
                # internal_blocks_data, restored just above) AND any other
                # block with a dynamic port count driven by its own params
                # (Scope, Mux, Demux, BusCreator, BusSelector, ...) -- it
                # must NOT be gated on "internal_blocks_data" being present,
                # or non-SubGraph dynamic-port blocks silently lose ports/
                # connections beyond their default count on load.
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

    @staticmethod
    def deserialize_annotations(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract free-text canvas annotations from a serialized graph.

        Kept separate from deserialize_graph (rather than added as a third
        tuple element) so existing `blocks, connections = deserialize_graph(...)`
        call sites don't all need updating -- annotations are plain dicts
        (no Qt, no id_map/connection wiring needed), so building them is a
        GUI-layer concern (constructing a UIAnnotation per entry).
        """
        annotations = []
        for entry in data.get("annotations", []):
            annotations.append({
                "text": entry.get("text", ""),
                "x": entry.get("x", 0.0),
                "y": entry.get("y", 0.0),
            })
        return annotations

    @staticmethod
    def deserialize_simulation_params(data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract simulation settings (duration, dt, solver) from a serialized
        graph. Returns an empty dict if the file predates this (or the
        caller didn't pass sim_params to serialize_graph) -- callers should
        only apply values that are actually present, leaving whatever the
        UI currently has untouched otherwise.
        """
        return dict(data.get("simulation", {}))
