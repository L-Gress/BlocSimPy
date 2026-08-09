"""Simulation engine for running block diagrams."""
import numpy as np
from typing import List, Dict, Any, Tuple
from ..models import BlockModel
from .executor import ExecutionOrdering
from .solvers import get_solver


class SimulationResult:
    """Container for simulation results."""
    
    def __init__(self):
        self.time: np.ndarray = np.array([])
        self.scope_data: Dict[str, Dict[str, Any]] = {}
        self.success: bool = False
        self.error_message: str = ""
    
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

    def configure(self, blocks: List[BlockModel], duration: float, dt: float, solver: str = "euler"):
        """Configure the simulation with blocks and parameters.

        solver: "euler" (default, forward Euler) or "rk4" (classic 4th-order
        Runge-Kutta, applied per-block -- see engine.simulation.solvers).
        """
        self.blocks = blocks
        self.duration = duration
        self.dt = dt
        self.solver = solver
    
    def run(self) -> SimulationResult:
        """
        Execute the simulation and return results.
        
        Returns:
            SimulationResult containing time and scope data
        """
        result = SimulationResult()
        
        try:
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

            # Main simulation loop
            solver = get_solver(self.solver)
            for t in time_vec:
                solver.step(sorted_blocks, stateful_blocks, t, self.dt)
            
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
