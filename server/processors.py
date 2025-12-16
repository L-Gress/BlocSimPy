import threading
import time
import sys
from engine.simulation.executor import ExecutionOrdering

class AudioProcessor:
    def __init__(self, blocks, sample_rate):
        self.blocks = blocks
        self.dt = 1.0 / sample_rate
        self.time = 0.0
        self.sorted_blocks = ExecutionOrdering.topological_sort(self.blocks)
        
        self.audio_inputs = []
        self.audio_outputs = []
        
        for b in self.sorted_blocks:
            if b.__class__.__name__ == "AudioInput":
                ch = int(b.params.get("Channel", 0))
                self.audio_inputs.append((b, ch))
            elif b.__class__.__name__ == "AudioOutput":
                ch = int(b.params.get("Channel", 0))
                self.audio_outputs.append((b, ch))

    def callback(self, indata, outdata, frames, time_info, status):
        if status:
            print(f"Stream Status: {status}", file=sys.stderr, flush=True)
            
        outdata.fill(0)
        
        dt = self.dt
        current_t = self.time
        sorted_blocks = self.sorted_blocks
        audio_inputs = self.audio_inputs
        audio_outputs = self.audio_outputs
        
        # Debug flag - only print every 100th callback to avoid spam
        # ~10 times per second if 44100Hz
        debug_this_callback = (int(current_t * 44100) % 4410) == 0  
        
        for i in range(frames):
            # 1. Read audio inputs
            for block, ch in audio_inputs:
                if ch < indata.shape[1]:
                    val = float(indata[i, ch])
                    block.outputs["out"].value = val
                    if debug_this_callback and i == 0:
                        print(f"[Audio IN] Ch{ch}: {val:.4f} -> {block.__class__.__name__}.out", flush=True)
            
            # 2. Compute all blocks
            for block in sorted_blocks:
                block.compute(current_t, dt)
                if hasattr(block, 'update_state'):
                    block.update_state(current_t, dt)
            
            # 3. Write audio outputs
            for block, ch in audio_outputs:
                if ch < outdata.shape[1]:
                    if "in" in block.inputs:
                        # Check if input is connected
                        input_port = block.inputs["in"]
                        val = input_port.value
                        
                        if debug_this_callback and i == 0:
                            connected_info = "CONNECTED" if input_port.connected_port else "DISCONNECTED"
                            print(f"[Audio OUT] Ch{ch}: {block.__class__.__name__}.in = {val:.4f} ({connected_info})", flush=True)
                        
                        outdata[i, ch] = val
                        
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
