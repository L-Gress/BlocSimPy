from ..models import BlockModel

class SubGraph(BlockModel):
    """
    A container block that holds an internal graph.
    Renamed from SubSystem to SubGraph.
    """
    
    BLOCK_INFO = {
        "description": "Container block holding internal block diagram",
        "parameters": "BlockName",
        "formula": "Executes internal diagram during simulation",
        "usage": "Organize complex systems, create reusable components, manage hierarchy. Double-click to enter/edit"
    }
    
    def __init__(self):
        super().__init__("SubGraph")
        
        # Use separate attributes to match scene_manager expectations
        self.internal_blocks_data = []
        self.internal_connections_data = []
        self.execution_blocks = []
        self.execution_map = {}
        
        # Default name parameter
        self.add_param("BlockName", "MySubGraph")
        
        # Initial label update
        self._update_label()

    def _update_label(self):
        """Formats the name to show Type on top, Name below."""
        user_name = self.params.get("BlockName", "MySubGraph")
        # The \n character forces a line break in QPainter.drawText
        self.name = f"SubGraph\n({user_name})"

    # Ensure label updates when parameters change (e.g. during loading)
    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        if name == "params" and hasattr(self, "_update_label"):
            self._update_label()

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._update_label()

    def sync_ports_from_data(self):
        """
        Reads internal_blocks_data to determine external inputs/outputs.
        """
        self.inputs.clear()
        self.outputs.clear()
        
        # Find InputPort and OutputPort blocks inside
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
        """Alias for sync_ports_from_data to match scene_manager expectations."""
        self.sync_ports_from_data()

    def reset(self):
        """Prepare internal blocks for simulation."""
        from . import BLOCK_REGISTRY
        
        self.execution_blocks = []
        self.execution_map = {}
        
        # Instantiate Internal Blocks
        for b_data in self.internal_blocks_data:
            b_type = b_data["type"]
            if b_type in BLOCK_REGISTRY:
                instance = BLOCK_REGISTRY[b_type]()
                instance.params = b_data["params"]
                if hasattr(instance, "reset"):
                    instance.reset()
                
                # Tag ports for data bridging
                if b_type == "InputPort": instance.is_subsystem_input = True
                if b_type == "OutputPort": instance.is_subsystem_output = True
                
                self.execution_blocks.append(instance)
                self.execution_map[b_data["id"]] = instance

        # Restore Internal Connections
        for c_data in self.internal_connections_data:
            source = self.execution_map.get(c_data["from_id"])
            target = self.execution_map.get(c_data["to_id"])
            if source and target:
                out_p = source.outputs.get(c_data["from_port"])
                in_p = target.inputs.get(c_data["to_port"])
                if out_p and in_p:
                    in_p.connected_port = out_p

    def compute(self, t, dt):
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
                    if "in" in b.inputs:
                        self.outputs[p_name].value = b.inputs["in"].value