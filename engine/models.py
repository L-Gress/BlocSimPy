import numpy as np
from typing import Dict, Any, Optional


class PortModel:
    def __init__(self, owner_block, name, is_input=True):
        self.owner = owner_block
        self.name = name
        self.is_input = is_input
        self._value = 0.0
        self.connected_port: Optional['PortModel'] = None

    @property
    def value(self):
        """
        Get the value on this port.
        If it's an input port and connected, fetch value from the source.
        """
        if self.is_input and self.connected_port:
            return self.connected_port.value
        return self._value

    @value.setter
    def value(self, val):
        self._value = val


class RuntimeContext:
    """Provides blocks with access to hardware buffers and external resources."""
    def __init__(self, indata=None, outdata=None, frame_idx=0):
        self.indata = indata
        self.outdata = outdata
        self.frame_idx = frame_idx


class BlockModel:
    """Base class for all simulation blocks."""
    def __init__(self, name: str):
        self.name = name
        self.id = id(self)
        self.inputs: Dict[str, PortModel] = {}
        self.outputs: Dict[str, PortModel] = {}
        self.params: Dict[str, Any] = {}
        self.state: np.ndarray = np.array([])
        self.is_container = False
        self.category = "Common"

    def add_input(self, name):
        self.inputs[name] = PortModel(self, name, True)

    def add_output(self, name):
        self.outputs[name] = PortModel(self, name, False)

    def add_param(self, name, value):
        self.params[name] = value

    def compute(self, t: float, dt: float, context: Optional[RuntimeContext] = None):
        """Standard update: Read inputs -> Calculate -> Write outputs."""
        pass

    def update_state(self, t: float, dt: float, context: Optional[RuntimeContext] = None):
        """For stateful blocks (integrators, etc)."""
        pass
