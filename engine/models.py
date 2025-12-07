import numpy as np
from typing import Dict, Any, Optional


class PortModel:
    def __init__(self, owner_block, name, is_input=True):
        self.owner = owner_block
        self.name = name
        self.is_input = is_input
        self.value = 0.0
        self.connected_port: Optional['PortModel'] = None


class BlockModel:
    """Base class for all simulation blocks."""
    def __init__(self, name: str):
        self.name = name
        self.id = id(self)
        self.inputs: Dict[str, PortModel] = {}
        self.outputs: Dict[str, PortModel] = {}
        self.params: Dict[str, Any] = {}
        self.state: np.ndarray = np.array([])

    def add_input(self, name):
        self.inputs[name] = PortModel(self, name, True)

    def add_output(self, name):
        self.outputs[name] = PortModel(self, name, False)

    def add_param(self, name, value):
        self.params[name] = value

    def compute(self, t: float, dt: float):
        """Standard update: Read inputs -> Calculate -> Write outputs."""
        pass

    def update_state(self, t: float, dt: float):
        """For stateful blocks (integrators, etc)."""
        pass
