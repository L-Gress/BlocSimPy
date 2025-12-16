import uuid
from engine.blocks import BLOCK_REGISTRY

def flatten_graph_and_connections(graph_data):
    """
    Recursively flattens a hierarchical graph.
    Returns:
      - all_blocks: A list of all instantiated block objects.
      - connections: A list of all connections (internal and boundary).
      - boundary_map: Mapping { (SubGraphID, PortName): InternalPortBlockInstance }
      - id_to_instance: Mapping { BlockID: BlockInstance }
    """
    all_blocks = []
    all_connections = []
    boundary_map = {} 
    id_to_instance = {}

    def process_level(blocks_data, connections_data):
        # 1. Instantiate Blocks
        for b_data in blocks_data:
            b_type = b_data["type"]
            b_id = b_data["id"]
            
            if b_type == "SubGraph":
                # Recurse
                process_level(
                    b_data.get("internal_blocks_data", []),
                    b_data.get("internal_connections_data", [])
                )
                
                # Map SubGraph ports to internal Port blocks
                for internal_b_data in b_data.get("internal_blocks_data", []):
                    if internal_b_data["type"] in ["InputPort", "OutputPort"]:
                        port_name = internal_b_data["params"].get("PortName")
                        internal_instance = id_to_instance.get(internal_b_data["id"])
                        if port_name and internal_instance:
                            boundary_map[(b_id, port_name)] = internal_instance

            elif b_type in BLOCK_REGISTRY:
                # Instantiate
                instance = BLOCK_REGISTRY[b_type]()
                instance.params = b_data.get("params", {}).copy()
                
                # FIX: Ensure ports have back-references to their parent block
                for port_model in instance.inputs.values():
                    port_model.block = instance
                for port_model in instance.outputs.values():
                    port_model.block = instance

                all_blocks.append(instance)
                id_to_instance[b_id] = instance
                
                if hasattr(instance, "reset"):
                    instance.reset()

        # 2. Collect Connections
        for c in connections_data:
            all_connections.append(c)

    process_level(graph_data.get("blocks", []), graph_data.get("connections", []))
    
    return all_blocks, all_connections, boundary_map, id_to_instance

def instantiate_graph(graph_data):
    """
    Reconstructs the graph, flattening SubGraphs and correctly wiring
    connections that cross SubGraph boundaries.
    """
    blocks, raw_connections, boundary_map, id_map = flatten_graph_and_connections(graph_data)
    
    # 1. Physical Connections (Block to Block within same level)
    #    and Virtual Linking (SubGraph to SubGraph)
    for c_data in raw_connections:
        source_id = c_data["from_block_id"]
        target_id = c_data["to_block_id"]
        source_port_name = c_data["from_port"]
        target_port_name = c_data["to_port"]

        # Resolve blocks (either direct ID or via Boundary Map)
        source_blk = id_map.get(source_id) or boundary_map.get((source_id, source_port_name))
        target_blk = id_map.get(target_id) or boundary_map.get((target_id, target_port_name))
        
        if source_blk and target_blk:
            
            # --- CASE A: Standard Connection (Block -> Block) ---
            # If both have valid physical ports, connect them.
            src_p = source_blk.outputs.get(source_port_name) or source_blk.outputs.get("out")
            dst_p = target_blk.inputs.get(target_port_name) or target_blk.inputs.get("in")
            
            if src_p and dst_p:
                dst_p.connected_port = src_p
            
            # --- CASE B: Boundary Connection (Crossing SubGraphs) ---
            # If we are connecting to an InputPort or from an OutputPort, physical ports might not exist.
            # We create a "Virtual Bridge" using a custom attribute `_virtual_source`.
            
            # If the Target is an InputPort block (inside a SubGraph), it receives data from Source
            if target_blk.__class__.__name__ == "InputPort":
                # We tag the InputPort with the block that feeds it from the outside
                target_blk._virtual_source = source_blk
                
                # If the Source was actually an OutputPort from another SubGraph, 
                # we might have failed the physical connection above.
                # The _virtual_source link preserves the chain.

            # Note: If Source is OutputPort, it has an 'in' but no 'out'. 
            # Logic flowing into it is handled by standard connections inside its SubGraph.
            # We only need to bridge the gap OUT of it (which is handled by the Target check above).

    # 2. Rewiring (Recursive Data Flow Resolution)
    # We walk backwards from every input. If we hit a Port block, we traverse the
    # virtual bridge or internal connection until we find a real Logic block.
    
    def get_real_source(port):
        if not port: return None
        parent = port.block
        
        # 1. Base Case: Standard Block (Sine, AudioInput, etc.)
        if parent.__class__.__name__ not in ["InputPort", "OutputPort", "RestInput"]:
            return port
            
        # 2. Recursive Case: OutputPort Block (Exit of a SubGraph)
        # It has an input 'in' that comes from inside the SubGraph.
        if parent.__class__.__name__ == "OutputPort":
            inp = parent.inputs.get("in")
            if inp and inp.connected_port:
                return get_real_source(inp.connected_port)
                
        # 3. Recursive Case: InputPort Block (Entry of a SubGraph)
        # It acts as a source for internal blocks, but gets data from `_virtual_source`
        if parent.__class__.__name__ == "InputPort":
            # Check for the virtual bridge we created in Step 1
            if hasattr(parent, "_virtual_source"):
                virtual_source_block = parent._virtual_source
                
                # The virtual source might be a standard block OR an OutputPort from another SG
                if virtual_source_block.__class__.__name__ == "OutputPort":
                    # Recurse into that OutputPort
                    # We can simulate having a port connection to it
                    # OutputPorts usually don't have outputs, so we pass the block to a helper or just recurse logic
                    # Let's check its input directly:
                    inp = virtual_source_block.inputs.get("in")
                    if inp and inp.connected_port:
                        return get_real_source(inp.connected_port)
                else:
                    # It's a standard block (e.g., Sine -> InputPort direct connection)
                    # Find its default output
                    out = virtual_source_block.outputs.get("out") or list(virtual_source_block.outputs.values())[0]
                    return out
        
        # 4. Handle RestInput (if it acts like a port)
        if parent.__class__.__name__ == "RestInput":
            # RestInput is usually a real source, so return it
            return port
            
        return None

    # Apply Rewiring to all blocks
    for block in blocks:
        for inp in block.inputs.values():
            if inp.connected_port:
                real_source = get_real_source(inp.connected_port)
                if real_source and real_source != inp.connected_port:
                    inp.connected_port = real_source
    
    # 3. Cleanup: Return only functional blocks
    final_blocks = [b for b in blocks if b.__class__.__name__ not in ["InputPort", "OutputPort"]]
    
    return final_blocks