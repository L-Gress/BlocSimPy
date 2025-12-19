import uuid
import sounddevice as sd
from utils import instantiate_graph
from processors import AudioProcessor, TimerProcessor
from state import deployments, server_lock

def deploy_graph_internal(data, dep_id=None, initial_status="Running"):
    """
    Internal function to deploy a graph.
    Returns the deployment ID.
    Raises Exception on failure.
    """
    config = data.get("config", {})
    graph_name = data.get("name", "Deployment")
    mode = config.get("execution_mode", "Auto Detect")
    
    # Instantiate Graph
    blocks = instantiate_graph(data["graph"])
    
    # Generic API Route Registration
    api_routes = {}
    for b in blocks:
        if hasattr(b, "register_api_routes"):
            try:
                routes = b.register_api_routes()
                if isinstance(routes, dict):
                    # We store the handler block/object for each relative path
                    for path, handler in routes.items():
                        # Prevent overlapping routes if necessary or just overwrite
                        api_routes[path] = handler
            except Exception as e:
                print(f"Warning: Failed to register API routes for block {b}: {e}", flush=True)

    # Determine Execution Mode
    has_audio_io = any(b.__class__.__name__ in ["AudioInput", "AudioOutput"] for b in blocks)
    
    final_mode = "Timer"
    if mode == "Audio Driven":
        final_mode = "Audio"
    elif mode == "Auto Detect":
        final_mode = "Audio" if has_audio_io else "Timer"
    
    dep_info = {}
    stream = None

    # --- AUDIO MODE ---
    if final_mode == "Audio":
        sample_rate = int(config.get("sample_rate", 44100))
        buffer_size = int(config.get("buffer_size", 1024))
        
        print(f"  Deploying [Audio Driver]: {graph_name} (Rate={sample_rate}, Buffer={buffer_size})", flush=True)
        
        # Device Selection
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
        
        processor = AudioProcessor(blocks, sample_rate)
        stream = sd.Stream(channels=2, samplerate=sample_rate, blocksize=buffer_size,
                            callback=processor.callback, device=(in_device, out_device),
                            latency='low')
        
        dep_info = {
            "type": "audio",
            "stream": stream, 
            "processor": processor,
            "config": config,
            "name": graph_name,
            "status": initial_status,
            "source_data": data,
            "api_routes": api_routes
        }
            
    # --- TIMER MODE ---
    else:
        rate = int(config.get("sample_rate", 100))
        batch = int(config.get("buffer_size", 1))
        
        print(f"  Deploying [Timer Driver]: {graph_name} (Rate={rate}Hz, Batch={batch})", flush=True)
        
        processor = TimerProcessor(blocks, rate, batch)
        
        dep_info = {
            "type": "timer",
            "stream": processor,
            "processor": processor,
            "config": config,
            "name": graph_name,
            "status": initial_status,
            "source_data": data,
            "api_routes": api_routes
        }
        stream = processor

    if not dep_id:
        dep_id = str(uuid.uuid4())[:8]

    with server_lock:
        deployments[dep_id] = dep_info
        if initial_status == "Running":
            stream.start()
            
    return dep_id
