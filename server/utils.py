import sys
import os

# Ensure engine is importable
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from engine.blocks import BLOCK_REGISTRY

def instantiate_graph(graph_data):
    """
    Reconstructs the graph from JSON data.
    """
    blocks = []
    id_map = {}
    
    for b_data in graph_data["blocks"]:
        b_type = b_data["type"]
        if b_type in BLOCK_REGISTRY:
            instance = BLOCK_REGISTRY[b_type]()
            instance.params = b_data["params"].copy()
            instance_id = b_data["id"]
            id_map[instance_id] = instance
            blocks.append(instance)
            
            if hasattr(instance, "reset"):
                instance.reset()
    
    for c_data in graph_data["connections"]:
        source = id_map.get(c_data["from_block_id"])
        target = id_map.get(c_data["to_block_id"])
        
        if source and target:
            out_p = source.outputs.get(c_data["from_port"])
            in_p = target.inputs.get(c_data["to_port"])
            
            if out_p and in_p:
                in_p.connected_port = out_p

    return blocks
