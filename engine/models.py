import numpy as np
from typing import Dict, Any, Optional


class PortModel:
    def __init__(self, owner_block, name, is_input=True):
        self.owner = owner_block
        self.name = name
        self.is_input = is_input
        self._value = 0.0
        self.connected_port: Optional['PortModel'] = None

        # Bus/vector signal state: N channels at ONE instant (e.g. Mux's
        # output).
        self.width = 1
        self._bus: Optional[np.ndarray] = None

    @property
    def value(self):
        """Get the value on this port: from the connected source if this is
        an input, else the locally-set value."""
        if self.is_input and self.connected_port:
            return self.connected_port.value
        return self._value

    @value.setter
    def value(self, val):
        self._value = val

    @property
    def bus_value(self) -> np.ndarray:
        """Get this port's bus/vector value: an array of N channel values at
        the current instant (e.g. what a Mux/Demux/BusCreator/BusSelector
        pass around).

        A port that was never explicitly given a bus value (e.g. a plain
        scalar block's output wired into a bus consumer by mistake) degrades
        to a harmless 1-wide array wrapping its scalar .value, consistent
        with this codebase's existing "no port type-checking, don't crash"
        philosophy -- see PortModel class docs / models.py header.
        """
        if self.is_input and self.connected_port:
            return self.connected_port.bus_value
        if self._bus is not None:
            return self._bus
        return np.array([self._value], dtype=float)

    @bus_value.setter
    def bus_value(self, arr):
        self._bus = np.asarray(arr, dtype=float)
        self.width = self._bus.size
        # Keep the plain scalar .value reader (Scope, or any block that
        # doesn't know about buses) from crashing/reading garbage.
        self._value = float(self._bus[0]) if self._bus.size else 0.0


class BlockModel:
    """Base class for all simulation blocks."""

    # Whether this block's compute() output for step k depends on its own
    # inputs' values at step k (vs. only on internal state set up by a prior
    # update_state() pass, like Integrator/Delay). Used by
    # ExecutionOrdering.topological_sort to distinguish real same-step
    # dependencies from state-broken feedback loops. True is the safe
    # default for any block that hasn't been audited.
    has_direct_feedthrough = True

    def feedthrough_pairs(self):
        """{output_port_name: {input_port_names with same-step feedthrough
        to it}} -- i.e. for each output, which inputs reading a fresh value
        could change it this step.

        Used by ExecutionOrdering.topological_sort for PER-(INPUT,OUTPUT)-
        PAIR (not just per-block) same-step dependency edges, combined with
        which of this block's outputs are actually read by something else
        in the diagram -- an unused output's feedthrough can't force an
        ordering on anyone. The default here derives from
        has_direct_feedthrough (all-or-nothing: every output depends on
        every input if True, none if False) and is correct for the vast
        majority of blocks -- anything with a single coupled input/output
        pair, or a fully state-broken one like Integrator/Delay.

        SubGraph overrides this with a precise per-pair analysis of its
        internal wiring: a container can easily have SOME input/output
        pairs coupled and others not (e.g. one output driven through a
        strictly-proper TF, another -- an unrelated diagnostic tap --
        driven straight through an algebraic path). Collapsing that to one
        block-wide (or even per-input-only) flag caused real false-positive
        algebraic-loop errors for exactly that shape of diagram.
        """
        if self.has_direct_feedthrough:
            all_inputs = set(self.inputs.keys())
            return {out_name: set(all_inputs) for out_name in self.outputs}
        return {out_name: set() for out_name in self.outputs}

    def __init__(self, name: str):
        self.name = name
        self.id = id(self)
        self.inputs: Dict[str, PortModel] = {}
        self.outputs: Dict[str, PortModel] = {}
        self.params: Dict[str, Any] = {}
        self.state: np.ndarray = np.array([])
        self.is_container = False
        self.category = "Common"

    def get_derivative(self, t: float, dt: float) -> Optional[np.ndarray]:
        """For ODE-like stateful blocks: return d(state)/dt at the block's
        CURRENT internal state, as a flat array, without mutating anything.
        Return None (the default) to opt out of solvers that need it (e.g.
        RK4Solver), in which case update_state() (Euler) is used instead.
        """
        return None

    def get_state(self) -> Optional[np.ndarray]:
        """Return the block's internal state as a flat array. Only needs to
        be implemented by blocks that implement get_derivative()."""
        return None

    def set_state(self, vec: np.ndarray):
        """Overwrite the block's internal state from a flat array produced
        by get_state()/derived from it. Only needs to be implemented by
        blocks that implement get_derivative()."""
        pass

    def add_input(self, name):
        self.inputs[name] = PortModel(self, name, True)

    def add_output(self, name):
        self.outputs[name] = PortModel(self, name, False)

    def add_param(self, name, value):
        self.params[name] = value

    def compute(self, t: float, dt: float, context=None):
        """Standard update: Read inputs -> Calculate -> Write outputs."""
        pass

    def update_state(self, t: float, dt: float, context=None):
        """For stateful blocks (integrators, etc)."""
        pass
