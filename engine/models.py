import numpy as np
from typing import Dict, Any, Optional


class PortModel:
    def __init__(self, owner_block, name, is_input=True):
        self.owner = owner_block
        self.name = name
        self.is_input = is_input
        self._value = 0.0
        self.connected_port: Optional['PortModel'] = None

        # Emulation State for legacy Loop support
        self._emulation_source: Optional[np.ndarray] = None
        self._emulation_idx = 0
        self._capture_buffer: Optional[np.ndarray] = None

        # Bus/vector signal state: N channels at ONE instant (e.g. Mux's
        # output). This is intentionally a SEPARATE field from vector_value/
        # _buffer above, which means "N time-samples of one channel" for the
        # audio chunk path -- conflating the two would corrupt whichever
        # path runs second.
        self.width = 1
        self._bus: Optional[np.ndarray] = None

    @property
    def value(self):
        """
        Get the value on this port.
        If emulation is active, return the specific sample from the chunk.
        Else if connected, fetch from source.
        """
        # 1. Emulation Mode (inside a loop)
        if self._emulation_source is not None:
             return self._emulation_source[self._emulation_idx]
        
        # 2. Standard Connection
        if self.is_input and self.connected_port:
            return self.connected_port.value
            
        return self._value

    @value.setter
    def value(self, val):
        self._value = val
        # 1. Emulation Mode (inside a loop)
        if self._capture_buffer is not None:
             self._capture_buffer[self._emulation_idx] = val
             return
             
        # 2. Hybrid Compatibility: DO NOT FILL BUFFER HERE
        # Filling buffer breaks interleaved execution.
        # Only specific blocks should manage buffer directly if not running emulated.

    @property
    def vector_value(self) -> np.ndarray:
        """
        Get the vectorized values for chunk processing.
        """
        if self.is_input and self.connected_port:
            return self.connected_port.vector_value
        return self._buffer

    @vector_value.setter
    def vector_value(self, val: np.ndarray):
        if not hasattr(self, '_buffer') or self._buffer.shape != val.shape:
            self._buffer = val.copy()
        else:
            self._buffer[:] = val
        # Sync scalar for compatibility
        self._value = val[-1] if val.size > 0 else 0.0

    def ensure_buffer(self, size: int):
        """Allocate or resize the internal buffer."""
        if not hasattr(self, '_buffer') or self._buffer.size != size:
            self._buffer = np.zeros(size)

    @property
    def bus_value(self) -> np.ndarray:
        """Get this port's bus/vector value: an array of N channel values at
        the current instant (e.g. what a Mux/Demux/BusCreator/BusSelector
        pass around). Distinct from vector_value (see __init__ note).

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


class RuntimeContext:
    """Provides blocks with access to hardware buffers and external resources."""
    def __init__(self, indata=None, outdata=None, frame_idx=0):
        self.indata = indata
        self.outdata = outdata
        self.frame_idx = frame_idx


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

    def compute(self, t: float, dt: float, context: Optional[RuntimeContext] = None):
        """Standard update: Read inputs -> Calculate -> Write outputs."""
        pass
        
    def compute_chunk(self, t_vec: np.ndarray, dt: float, context: Optional[RuntimeContext] = None):
        """
        Process a chunk of samples. 
        Default implementation provides backward compatibility via a loop with scalar emulation.
        """
        # 1. Setup Emulation for Inputs
        active_inputs = []
        for p in self.inputs.values():
            if p.connected_port:
                # We need to read from the UPSTREAM vector
                # Ensure upstream has a buffer (it should if it ran compute_chunk)
                # If upstream is legacy, it might not have run vector logic? 
                # Assumption: Scheduler runs compute_chunk for all blocks. 
                # Even legacy blocks will produce a "capture buffer" (see below).
                src = p.connected_port.vector_value
                p._emulation_source = src
                p._emulation_idx = 0
                active_inputs.append(p)
                
        # 2. Setup Capture for Outputs
        active_outputs = []
        for p in self.outputs.values():
            p.ensure_buffer(len(t_vec))
            p._capture_buffer = p._buffer
            p._emulation_idx = 0
            active_outputs.append(p)

        # 3. Execution Loop
        for i, t in enumerate(t_vec):
            # Update indices
            for p in active_inputs: p._emulation_idx = i
            for p in active_outputs: p._emulation_idx = i
            
            if context: context.frame_idx = i
            
            self.compute(t, dt, context)
            
        # 4. Cleanup
        for p in active_inputs: p._emulation_source = None
        for p in active_outputs: p._capture_buffer = None

    def update_state(self, t: float, dt: float, context: Optional[RuntimeContext] = None):
        """For stateful blocks (integrators, etc)."""
        pass

    def update_state_chunk(self, t_vec: np.ndarray, dt: float, context: Optional[RuntimeContext] = None):
        """
        Process a chunk of state updates.
        Default implementation provides backward compatibility via a loop with scalar emulation.
        """
        # 1. Setup Emulation for Inputs (State update might need inputs)
        active_inputs = []
        for p in self.inputs.values():
            if p.connected_port:
                src = p.connected_port.vector_value
                p._emulation_source = src
                p._emulation_idx = 0
                active_inputs.append(p)

        # Reset frame_idx for the state update pass if context exists
        if context:
            original_idx = context.frame_idx
            
        for i, t in enumerate(t_vec):
            # Update indices
            for p in active_inputs: p._emulation_idx = i
            
            if context:
                context.frame_idx = i
                
            self.update_state(t, dt, context)
            
        if context:
            context.frame_idx = original_idx

        # 4. Cleanup
        for p in active_inputs: p._emulation_source = None
