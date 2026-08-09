"""Pluggable step solvers for SimulationEngine.

Each solver implements one thing: given the already topologically-sorted
blocks for a step at time t, advance the simulation by dt. Every block's
algebraic output (compute()) is always evaluated exactly once per step,
in sorted order -- this is required because some blocks have side effects
per compute() call (Scope recording, SubGraph queues), so calling compute()
more than once per step per block would corrupt those. Only state
integration (update_state(), or a higher-order scheme via
get_derivative()/get_state()/set_state()) varies between solvers.
"""
from typing import List
import numpy as np
from ..models import BlockModel


class Solver:
    """Base class for step solvers."""

    name = "base"

    def step(self, sorted_blocks: List[BlockModel], stateful_blocks: List[BlockModel], t: float, dt: float):
        raise NotImplementedError


class EulerSolver(Solver):
    """Forward Euler. Behaviorally identical to the engine's original
    (pre-solver-abstraction) inline loop: compute() everything, then
    update_state() everything."""

    name = "euler"

    def step(self, sorted_blocks, stateful_blocks, t, dt):
        for block in sorted_blocks:
            block.compute(t, dt)
        for block in stateful_blocks:
            block.update_state(t, dt)


class RK4Solver(Solver):
    """Classic 4th-order Runge-Kutta, applied per-block to any block that
    implements get_derivative()/get_state()/set_state().

    Design note: this does NOT re-run the whole graph's compute() at each
    of the 4 RK4 stages (that would require re-propagating every algebraic
    block's output through fractional-time inputs, and would call
    side-effecting compute() methods -- like Scope's data recording --
    multiple times per step). Instead, each stateful block is integrated
    against its OWN derivative function with its current input held
    constant over the step (a zero-order-hold assumption). This is exact
    for a block driven by a constant or slowly-varying input and is still
    a real accuracy improvement over Euler for typical dt, without any of
    the side-effect-duplication hazard.

    Blocks that don't implement get_derivative() (it returns None, the
    BlockModel default) -- e.g. Delay, Rate Limiter, anything with purely
    discrete state -- fall back to their own update_state() (Euler),
    exactly as EulerSolver would.
    """

    name = "rk4"

    def step(self, sorted_blocks, stateful_blocks, t, dt):
        for block in sorted_blocks:
            block.compute(t, dt)

        for block in stateful_blocks:
            k1 = block.get_derivative(t, dt)
            if k1 is None:
                block.update_state(t, dt)
                continue
            k1 = np.asarray(k1, dtype=float)
            if k1.size == 0:
                # Nothing to integrate (e.g. a TransferFunction with no
                # internal states); update_state() is a safe no-op here.
                block.update_state(t, dt)
                continue

            x0 = np.asarray(block.get_state(), dtype=float)

            block.set_state(x0 + (dt / 2.0) * k1)
            k2 = np.asarray(block.get_derivative(t + dt / 2.0, dt), dtype=float)

            block.set_state(x0 + (dt / 2.0) * k2)
            k3 = np.asarray(block.get_derivative(t + dt / 2.0, dt), dtype=float)

            block.set_state(x0 + dt * k3)
            k4 = np.asarray(block.get_derivative(t + dt, dt), dtype=float)

            x_new = x0 + (dt / 6.0) * (k1 + 2.0 * k2 + 2.0 * k3 + k4)
            block.set_state(x_new)


SOLVERS = {
    "euler": EulerSolver,
    "rk4": RK4Solver,
}


def get_solver(name: str) -> Solver:
    return SOLVERS.get(name, EulerSolver)()
