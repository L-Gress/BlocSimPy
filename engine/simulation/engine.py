"""Simulation engine for running block diagrams."""
import numpy as np
from typing import List, Dict, Any, Tuple
from ..models import BlockModel
from ..variables import resolve_params, find_variable_refs, get_active_variables, set_active_variables
from .executor import ExecutionOrdering, AlgebraicLoopError
from .solvers import get_solver


class SimulationResult:
    """Container for simulation results."""

    def __init__(self):
        self.time: np.ndarray = np.array([])
        self.scope_data: Dict[str, Dict[str, Any]] = {}
        self.success: bool = False
        self.error_message: str = ""
        self.cancelled: bool = False
    
    def add_scope_data(self, scope_name: str, time: np.ndarray, data: np.ndarray):
        """Add data from a scope block."""
        self.scope_data[scope_name] = {
            'time': time,
            'data': data
        }


class SimulationEngine:
    """Main simulation engine that executes block diagrams."""
    
    def __init__(self):
        self.blocks: List[BlockModel] = []
        self.duration: float = 10.0
        self.dt: float = 0.01
        self.solver: str = "euler"
        # The global variable store (see engine/variables.py) every
        # variable-bound param resolves against -- defaults to whatever is
        # currently registered (the real app's global variables, or {} for
        # headless/test code that never registered one).
        self.variables: Dict[str, Any] = get_active_variables()

    def configure(self, blocks: List[BlockModel], duration: float, dt: float, solver: str = "euler",
                  variables: Dict[str, Any] = None):
        """Configure the simulation with blocks and parameters.

        solver: "euler" (default, forward Euler) or "rk4" (classic 4th-order
        Runge-Kutta, applied per-block -- see engine.simulation.solvers).

        variables: optional override for the global variable store (see
        engine/variables.py) -- passing one also RE-registers it via
        set_active_variables(), so a SubGraph's own nested resolution
        (which has no direct way to receive `self.variables`, since
        reset() takes no arguments) stays in sync with it. Omit to just use
        whatever's already registered (the normal app path -- see
        ScriptManager.__init__).
        """
        self.blocks = blocks
        self.duration = duration
        self.dt = dt
        self.solver = solver
        if variables is not None:
            set_active_variables(variables)
        self.variables = get_active_variables()
    
    def run(self, progress_callback=None, should_cancel=None) -> SimulationResult:
        """
        Execute the simulation and return results.

        progress_callback: optional callable(fraction: float) invoked
        periodically (not every step, to keep overhead low) with progress
        in [0, 1]. should_cancel: optional callable() -> bool, polled at the
        same cadence; if it returns True the run stops early and the result
        is marked `cancelled`. Both are no-ops by default so headless/batch
        callers (tests, CLI use) are unaffected.

        Returns:
            SimulationResult containing time and scope data
        """
        result = SimulationResult()
        original_params = {}

        try:
            # Swap in resolved values for every variable-bound param (see
            # engine/variables.py) BEFORE topological_sort() below -- some
            # blocks' has_direct_feedthrough (TransferFunction, StateSpace,
            # ...) is a live property computed FROM their own params, which
            # topological_sort() reads for algebraic-loop detection; sorting
            # against still-unresolved reference dicts would (best case)
            # order the diagram against the wrong feedthrough info, not
            # just fail to compute a value yet. Restored in `finally`
            # below, so the live/design params (references intact) are
            # exactly what they were before Run regardless of success/
            # failure/cancellation -- callers are expected to have already
            # blocked the run on any `missing` name via
            # check_diagram_detailed() (see ToolbarManager.run_simulation()/
            # ScriptManager.sim()), so anything still unresolved here is
            # passed through as-is rather than silently defaulted to 0.0.
            for block in self.blocks:
                if hasattr(block, "params"):
                    resolved, _missing = resolve_params(block.params, self.variables)
                    if resolved is not block.params:
                        original_params[block] = block.params
                        block.params = resolved

            # Sort blocks in execution order
            sorted_blocks = ExecutionOrdering.topological_sort(self.blocks)

            # Reset all block states
            for block in sorted_blocks:
                if hasattr(block, 'reset'):
                    block.reset()
                if hasattr(block, 'time_data'):
                    block.time_data = []
                if hasattr(block, 'value_data'):
                    block.value_data = []

            # Time vector
            time_vec = np.arange(0, self.duration, self.dt)
            result.time = time_vec

            # Cache stateful blocks to avoid hasattr() every step
            stateful_blocks = [b for b in sorted_blocks if hasattr(b, 'update_state')]

            # Main simulation loop. Progress/cancellation are only checked
            # every `report_every` steps (~200 updates over the whole run)
            # so they don't add per-step overhead to tight loops.
            solver = get_solver(self.solver)
            total_steps = len(time_vec)
            report_every = max(1, total_steps // 200)
            for i, t in enumerate(time_vec):
                if should_cancel is not None and i % report_every == 0 and should_cancel():
                    result.success = False
                    result.cancelled = True
                    result.error_message = "Simulation cancelled."
                    return result

                solver.step(sorted_blocks, stateful_blocks, t, self.dt)

                if progress_callback is not None and (i % report_every == 0 or i == total_steps - 1):
                    progress_callback((i + 1) / total_steps)

            # Collect scope data
            for block in sorted_blocks:
                if block.__class__.__name__ == "Scope":
                    if hasattr(block, 'time_data') and hasattr(block, 'value_data'):
                        block_name = block.params.get("BlockName", block.name)
                        result.add_scope_data(
                            block_name,
                            np.array(block.time_data),
                            np.array(block.value_data)
                        )
            
            result.success = True
            
        except Exception as e:
            result.success = False
            result.error_message = str(e)
        finally:
            for block, params in original_params.items():
                block.params = params

        return result
    
    def validate(self) -> "Tuple[bool, str]":
        """
        Validate the simulation configuration.
        
        Returns:
            (is_valid, error_message)
        """
        if self.dt <= 0:
            return False, "Time step must be positive"
        
        if self.duration <= 0:
            return False, "Duration must be positive"
        
        if self.dt > self.duration:
            return False, "Time step cannot be larger than duration"
        
        if not self.blocks:
            return False, "No blocks in simulation"

        return True, ""

    def check_diagram(self) -> "List[str]":
        """
        "Update Diagram" pre-flight check: surfaces structural problems
        before Run, rather than failing mid-simulation (or, for unconnected
        inputs, not failing at all -- silently reading 0.0). Separate from
        validate() (dt/duration/block-list sanity), which is unchanged.

        Each issue is a human-readable string prefixed "ERROR:" (blocking --
        Run cannot proceed, e.g. an algebraic loop) or "WARNING:" (non-
        blocking, e.g. an unconnected input -- that's existing, sometimes-
        intentional behavior, so it doesn't suddenly hard-block diagrams
        that already work today).
        """
        return [f"{d['level']}: {d['message']}" for d in self.check_diagram_detailed()]

    def check_diagram_detailed(self) -> "List[Dict[str, Any]]":
        """Structured version of check_diagram(), for callers that want to
        locate the offending block(s) (e.g. a GUI selecting/centering them
        on canvas) rather than just display the message. Each issue is
        {"level": "ERROR"|"WARNING", "message": str, "blocks": [block_name, ...]}.
        check_diagram() derives its plain-string form from this."""
        issues: "List[Dict[str, Any]]" = []

        try:
            ExecutionOrdering.topological_sort(self.blocks)
        except AlgebraicLoopError as e:
            names = [b.params.get("BlockName", b.name) if hasattr(b, "params") else b.name for b in e.blocks]
            issues.append({"level": "ERROR", "message": str(e), "blocks": names})

        for block in self.blocks:
            block_name = block.params.get("BlockName", block.name) if hasattr(block, "params") else block.name
            for port_name, port in block.inputs.items():
                if port.connected_port is None:
                    issues.append({
                        "level": "WARNING",
                        "message": f"{block_name}.{port_name} is not connected (will read 0.0)",
                        "blocks": [block_name],
                    })

            if hasattr(block, "params"):
                self._check_missing_variables(block_name, block.params, issues)
            nested = getattr(block, "internal_blocks_data", None)
            if nested:
                self._check_missing_variables_nested(block_name, nested, issues)

        return issues

    def _check_missing_variables(self, block_label: str, params: Dict[str, Any], issues: "List[Dict[str, Any]]"):
        """Flag every parameter on one block bound (see engine/variables.py)
        to a name not currently in self.variables -- a typo, a forgotten
        setup Script, or a variable that was renamed/cleared since the
        param was bound. Blocking (ERROR), not a warning: Run swaps this
        value in for the whole simulation (see run()), so an undeclared
        reference is never worth guessing a default for."""
        for param_name, var_name in find_variable_refs(params).items():
            if var_name not in self.variables:
                issues.append({
                    "level": "ERROR",
                    "message": f"{block_label}.{param_name} references undeclared variable '{var_name}'",
                    "blocks": [block_label],
                })

    def _check_missing_variables_nested(self, path_prefix: str, blocks_data: "List[Dict[str, Any]]",
                                         issues: "List[Dict[str, Any]]"):
        """Same check as _check_missing_variables(), recursively over a
        SubGraph's raw internal_blocks_data (and any SubGraph nested inside
        THAT, arbitrarily deep) -- those blocks are only ever instantiated
        as ephemeral execution_blocks inside SubGraph.reset(), so they're
        not in self.blocks and need their own pass over the design-time
        dicts instead of a live block's .params."""
        for b_data in blocks_data:
            label = f"{path_prefix}/{b_data.get('params', {}).get('BlockName', b_data.get('type', '?'))}"
            self._check_missing_variables(label, b_data.get("params", {}), issues)
            nested = b_data.get("internal_blocks_data")
            if nested:
                self._check_missing_variables_nested(label, nested, issues)
