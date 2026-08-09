"""Shared pytest configuration and helpers for the BlocSimPy engine test suite."""
import os
import sys

# Ensure the project root is importable regardless of how pytest was invoked.
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)


def connect(dst_block, dst_port, src_block, src_port="out"):
    """Wire src_block.outputs[src_port] -> dst_block.inputs[dst_port]."""
    dst_block.inputs[dst_port].connected_port = src_block.outputs[src_port]


def set_params(block, **kwargs):
    """Set params and retrigger any per-block param-cache refresh hooks.

    Several blocks (Gain, Constant, Delay, SineWave, Integrator, AudioInput/
    Output, ...) parse/cache their params for performance, refreshed only
    when the whole `params` dict object is reassigned (see each block's
    __setattr__). Mutating block.params[key] in place silently skips that
    refresh. This mirrors what GraphSerializer and the blocks' own editor
    dialogs do, so tests exercise the same contract real callers rely on.
    """
    block.params.update(kwargs)
    block.params = block.params


def step(blocks, t, dt):
    """Run one compute + update_state pass over blocks, in the given order."""
    for b in blocks:
        b.compute(t, dt)
    for b in blocks:
        if hasattr(b, "update_state"):
            b.update_state(t, dt)
