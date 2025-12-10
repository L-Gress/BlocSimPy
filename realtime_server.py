
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
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

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
                sample_rate = int(config.get("sample_rate", 44100))
                buffer_size = int(config.get("buffer_size", 1024))
                graph_name = data.get("name", "Deployment")
                
                print(f"  Deploying: {graph_name} (Rate={sample_rate}, Buffer={buffer_size})", flush=True)
                
                # --- Debug: Dump Graph JSON ---
                # print(f"  [DEBUG] Graph Data: {json.dumps(data['graph'], indent=2)}", flush=True)

                blocks = instantiate_graph(data["graph"])
                
                # --- Debug: List Blocks & Connections ---
                print("  [DEBUG] Instantiated Blocks:", flush=True)
                for b in blocks:
                    print(f"    - {b.__class__.__name__} (ID={b.id if hasattr(b,'id') else '?'}) Params={b.params}", flush=True)

                print("  [DEBUG] Connection Logic:", flush=True)
                for b in blocks:
                    for name, port in b.inputs.items():
                        if port.connected_port:
                            p_curr = f"{b.__class__.__name__}.{name}"
                            # Try to find owner of connected port
                            # This is reverse lookup just for debug print
                            connected_block_name = "Unknown"
                            for other in blocks:
                                for oname, oport in other.outputs.items():
                                    if oport == port.connected_port:
                                        connected_block_name = f"{other.__class__.__name__}.{oname}"
                            print(f"    Link: {connected_block_name} -> {p_curr}", flush=True)
                
                # --- Debug: List Blocks ---
                print("  [DEBUG] Instantiated Blocks:", flush=True)
                for b in blocks:
                    b_id = getattr(b, 'id', 'unknown') # BlockModel might not store ID by default unless added
                    # Actually graph_data['blocks'] had IDs. instantiate_graph uses them but might not set attribute on instance?
                    # instantiate_graph (line 46) does: id_map[instance_id] = instance. It doesn't set instance.id = instance_id usually.
                    # Let's check instantiate_graph implementation in previous turn. 
                    # It does NOT set instance.id.
                    
                    # Just print class name and params
                    print(f"    - {b.__class__.__name__}: {b.params}", flush=True)
                
                # --- Device Selection Logic ---
                in_device = None
                out_device = None
                
                def parse_device(val):
                    if not val or val == "default": return None
                    try: return int(val)
                    except ValueError: return val # Return valid string
                
                for b in blocks:
                    if b.__class__.__name__ == "AudioInput":
                        dev_param = b.params.get("Device")
                        parsed = parse_device(dev_param)
                        if parsed is not None:
                            if in_device is not None and in_device != parsed:
                                print(f"  Warning: Conflicting Input Devices ({in_device} vs {parsed}). Using {in_device}.", flush=True)
                            else:
                                in_device = parsed
                                
                    elif b.__class__.__name__ == "AudioOutput":
                        dev_param = b.params.get("Device")
                        parsed = parse_device(dev_param)
                        if parsed is not None:
                            if out_device is not None and out_device != parsed:
                                print(f"  Warning: Conflicting Output Devices ({out_device} vs {parsed}). Using {out_device}.", flush=True)
                            else:
                                out_device = parsed
                
                print(f"  Selected Devices -> In: {in_device}, Out: {out_device}", flush=True)
                
                processor = AudioProcessor(blocks, sample_rate)
                
                stream = sd.Stream(
                    channels=2, 
                    samplerate=sample_rate,
                    blocksize=buffer_size,
                    callback=processor.callback,
                    device=(in_device, out_device)
                )
                
                dep_id = str(uuid.uuid4())[:8] 
                
                with server_lock:
                    deployments[dep_id] = {
                        "stream": stream,
                        "processor": processor,
                        "config": config,
                        "name": graph_name,
                        "status": "Running"
                    }
                    stream.start()
                
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
                        stream.close()
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
