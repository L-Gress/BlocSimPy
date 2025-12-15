
import http.server
import json
import threading
import sys
import time
import uuid
import numpy as np
import traceback
import sounddevice as sd
import os

# Add parent directory to path to allow importing 'engine'
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.append(parent_dir)

from engine.blocks import BLOCK_REGISTRY
from engine.simulation.executor import ExecutionOrdering

# --- Global State ---
deployments = {}
server_lock = threading.Lock()

def instantiate_graph(graph_data):
    """
    Reconstructs the graph from JSON data.
    """
    blocks = []
    id_map = {}
    
    for b_data in graph_data["blocks"]:
        b_type = b_data["type"]
        if b_type in BLOCK_REGISTRY:
            instance = BLOCK_REGISTRY[b_type]()
            instance.params = b_data["params"].copy()
            instance_id = b_data["id"]
            id_map[instance_id] = instance
            blocks.append(instance)
            
            if hasattr(instance, "reset"):
                instance.reset()
    
    for c_data in graph_data["connections"]:
        source = id_map.get(c_data["from_block_id"])
        target = id_map.get(c_data["to_block_id"])
        
        if source and target:
            out_p = source.outputs.get(c_data["from_port"])
            in_p = target.inputs.get(c_data["to_port"])
            
            if out_p and in_p:
                in_p.connected_port = out_p

    return blocks

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
        debug_this_callback = (int(current_t * 44100) % 4410) == 0  # ~10 times per second
        
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
        self.thread = threading.Thread(target=self._run_loop)
        self.thread.start()
        
    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join()
            
    def close(self):
        self.stop()

    def _run_loop(self):
        print(f"Timer Processor Started: {self.rate}Hz (Batch={self.steps_per_batch})", flush=True)
        next_run = time.time()
        
        while self.running:
            now = time.time()
            if now >= next_run:
                # Catch up logic? No, simple skip if too slow
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

class RequestHandler(http.server.BaseHTTPRequestHandler):
    
    def log_message(self, format, *args):
        # Override to ensure flush
        sys.stderr.write("%s - - [%s] %s\n" %
                         (self.client_address[0],
                          self.log_date_time_string(),
                          format % args))
        sys.stderr.flush()

    def _send_json(self, data, code=200):
        self.send_response(code)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*') 
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
        
    def do_GET(self):
        print(f"GET request: {self.path}", flush=True)
        if self.path == "/deployments":
            with server_lock:
                summary = []
                for dep_id, info in deployments.items():
                    name = info.get("name", "Untitled")
                    summary.append({
                        "id": dep_id,
                        "name": name,
                        "status": info["status"],
                        "config": info["config"]
                    })
                self._send_json(summary)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        print(f"POST request: {self.path}", flush=True)
        content_len = int(self.headers.get('Content-Length', 0))
        post_body = self.rfile.read(content_len)
        try:
            data = json.loads(post_body)
        except json.JSONDecodeError:
            self._send_json({"error": "Invalid JSON"}, 400)
            return
        
        if self.path == "/deploy":
            try:
                config = data.get("config", {})
                
                # Generic Parameters
                graph_name = data.get("name", "Deployment")
                mode = config.get("execution_mode", "Auto Detect")
                
                # Instantiate Graph
                blocks = instantiate_graph(data["graph"])
                
                # Determine Execution Mode
                has_audio_io = any(b.__class__.__name__ in ["AudioInput", "AudioOutput"] for b in blocks)
                
                final_mode = "Timer"
                if mode == "Audio Driven":
                    final_mode = "Audio"
                elif mode == "Auto Detect":
                    final_mode = "Audio" if has_audio_io else "Timer"
                
                # --- AUDIO MODE ---
                if final_mode == "Audio":
                    sample_rate = int(config.get("sample_rate", 44100))
                    buffer_size = int(config.get("buffer_size", 1024))
                    
                    print(f"  Deploying [Audio Driver]: {graph_name} (Rate={sample_rate}, Buffer={buffer_size})", flush=True)
                    
                    # Device Selection (Existing Logic simplified)
                    in_device = None; out_device = None
                    try:
                        for b in blocks:
                            dev = b.params.get("Device")
                            if not dev or dev == "default": continue
                            try: val = int(dev)
                            except: val = dev
                            if b.__class__.__name__ == "AudioInput": in_device = val
                            elif b.__class__.__name__ == "AudioOutput": out_device = val
                    except: pass
                    
                    # Create Processor
                    processor = AudioProcessor(blocks, sample_rate)
                    stream = sd.Stream(channels=2, samplerate=sample_rate, blocksize=buffer_size,
                                     callback=processor.callback, device=(in_device, out_device))
                    
                    dep_id = str(uuid.uuid4())[:8]
                    with server_lock:
                        deployments[dep_id] = {
                            "type": "audio",
                            "stream": stream, 
                            "processor": processor,
                            "config": config,
                            "name": graph_name,
                            "status": "Running"
                        }
                        stream.start()
                        
                # --- TIMER MODE ---
                else:
                    rate = int(config.get("sample_rate", 100)) # Default 100Hz for timer
                    batch = int(config.get("buffer_size", 1))  # Default 1 step per loop
                    
                    print(f"  Deploying [Timer Driver]: {graph_name} (Rate={rate}Hz, Batch={batch})", flush=True)
                    
                    processor = TimerProcessor(blocks, rate, batch)
                    
                    dep_id = str(uuid.uuid4())[:8]
                    with server_lock:
                        deployments[dep_id] = {
                            "type": "timer",
                            "stream": processor, # Interface match
                            "processor": processor,
                            "config": config,
                            "name": graph_name,
                            "status": "Running"
                        }
                        processor.start()

                print(f"  -> Success: {dep_id}", flush=True)
                self._send_json({"id": dep_id, "message": "Deployed successfully"})
                
            except Exception as e:
                error_msg = traceback.format_exc()
                print(f"  -> Failed: {e}\n{error_msg}", flush=True)
                self._send_json({"error": str(e), "traceback": error_msg}, 500)

        elif self.path == "/control":
            action = data.get("action")
            dep_id = data.get("id")
            
            print(f"  Control Action: {action} on {dep_id}", flush=True)
            
            with server_lock:
                if dep_id not in deployments:
                    self._send_json({"error": "Deployment not found"}, 404)
                    return
                    
                info = deployments[dep_id]
                stream = info["stream"]
                
                try:
                    if action == "stop":
                        if info["status"] == "Running":
                            stream.stop()
                            info["status"] = "Stopped"
                            
                    elif action == "start":
                        if info["status"] == "Stopped":
                            stream.start()
                            info["status"] = "Running"
                            
                    elif action == "delete":
                        stream.stop()
                        if hasattr(stream, 'close'): stream.close()
                        del deployments[dep_id]
                        print(f"  Deleted {dep_id}", flush=True)
                        
                    self._send_json({"message": f"Action {action} completed"})
                except Exception as e:
                    print(f"  Control Error: {e}", flush=True)
                    self._send_json({"error": str(e)}, 500)
                    
        else:
            self.send_response(404)
            self.end_headers()

def run_server(port=8080):
    server_address = ('', port)
    httpd = http.server.HTTPServer(server_address, RequestHandler)
    print(f"Realtime Server (Multi-Session) listening on port {port}...", flush=True)
    print("Buffer log initialized.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 8080
    run_server(port)
