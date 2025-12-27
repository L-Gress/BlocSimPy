import threading
import time
import sys
from engine.simulation.executor import ExecutionOrdering
import numpy as np

from engine.models import RuntimeContext

class AudioProcessor:
    def __init__(self, blocks, sample_rate):
        self.blocks = blocks
        self.dt = 1.0 / sample_rate
        self.time = 0.0
        self.sorted_blocks = ExecutionOrdering.topological_sort(self.blocks)
        
        # Pre-filter blocks that have update_state to avoid hasattr in callback
        self.stateful_blocks = [b for b in self.sorted_blocks if hasattr(b, 'update_state')]
        
        # Pre-allocate RuntimeContext
        self.ctx = RuntimeContext()
        
        # Ensure all ports have buffers allocated (optional but good for stability)
        # We use a default block size, but ports will resize if needed.
        self._initial_block_size = 1024 # Placeholder, actual frames will be used in callback
        
    def callback(self, indata, outdata, frames, time_info, status):
        """Audio callback running in a high-priority hardware thread."""
        if status:
            try:
                print(f"Stream Status: {status}", file=sys.stderr, flush=True)
            except:
                pass
            
        # 1. Prepare Time Vector and Context
        dt = self.dt
        current_t = self.time
        t_vec = current_t + np.arange(frames) * dt
        
        ctx = self.ctx
        ctx.indata = indata
        ctx.outdata = outdata
        ctx.frame_idx = 0
        
        # 2. Ensure all port buffers match the current frame count
        for block in self.sorted_blocks:
            for port in block.inputs.values():
                port.ensure_buffer(frames)
            for port in block.outputs.values():
                port.ensure_buffer(frames)

        # 3. Vectorized Computation Pass
        for block in self.sorted_blocks:
            block.compute_chunk(t_vec, dt, context=ctx)
        
        # 4. Vectorized State Update Pass
        for block in self.stateful_blocks:
            block.update_state_chunk(t_vec, dt, context=ctx)
            
        self.time = current_t + frames * dt

class TimerProcessor:
    """Runs simulation based on system clock (independent of audio hardware)."""
    def __init__(self, blocks, rate, steps_per_batch=1):
        self.blocks = blocks
        self.dt = 1.0 / rate
        self.rate = rate
        self.time = 0.0
        self.steps_per_batch = steps_per_batch
        self.sorted_blocks = ExecutionOrdering.topological_sort(self.blocks)
        
        # Determine strict sleep time
        self.target_interval = self.dt * self.steps_per_batch
        
        self.running = False
        self.thread = None
        
    def start(self):
        self.running = True
        # Set daemon=True to ensure thread dies when main thread exits
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.0)
            
    def close(self):
        self.stop()

    def _run_loop(self):
        print(f"Timer Processor Started: {self.rate}Hz (Batch={self.steps_per_batch})", flush=True)
        next_run = time.time()
        
        while self.running:
            now = time.time()
            if now >= next_run:
                # Execute Batch
                for _ in range(self.steps_per_batch):
                    for block in self.sorted_blocks:
                        block.compute(self.time, self.dt)
                        if hasattr(block, 'update_state'):
                            block.update_state(self.time, self.dt)
                    self.time += self.dt
                
                next_run += self.target_interval
                
                # If we're really far behind, reset
                if time.time() > next_run + 1.0:
                    next_run = time.time()
            else:
                sleep_time = next_run - now
                if sleep_time > 0.001:
                    time.sleep(sleep_time)

    # Mock stream interface for compatibility
    def is_active(self): return self.running
