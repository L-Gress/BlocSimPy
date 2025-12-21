import threading
import time
import sys
from engine.simulation.executor import ExecutionOrdering

from engine.models import RuntimeContext

class AudioProcessor:
    def __init__(self, blocks, sample_rate):
        self.blocks = blocks
        self.dt = 1.0 / sample_rate
        self.time = 0.0
        self.sorted_blocks = ExecutionOrdering.topological_sort(self.blocks)
        
        # Pre-filter blocks that have update_state to avoid hasattr in callback
        self.stateful_blocks = [b for b in self.sorted_blocks if hasattr(b, 'update_state')]
        
    def callback(self, indata, outdata, frames, time_info, status):
        """Audio callback running in a high-priority hardware thread."""
        if status:
            print(f"Stream Status: {status}", file=sys.stderr, flush=True)
            
        outdata.fill(0)
        
        dt = self.dt
        current_t = self.time
        sorted_blocks = self.sorted_blocks
        stateful_blocks = self.stateful_blocks
        
        # We reuse one context object to avoid allocations
        ctx = RuntimeContext(indata=indata, outdata=outdata, frame_idx=0)
        
        for i in range(frames):
            ctx.frame_idx = i
            
            # 1. Compute all blocks (Includes Audio IO blocks via context)
            for block in sorted_blocks:
                block.compute(current_t, dt, context=ctx)
            
            # 2. Update state for stateful blocks
            for block in stateful_blocks:
                block.update_state(current_t, dt, context=ctx)
                
            current_t += dt
            
        self.time = current_t

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
