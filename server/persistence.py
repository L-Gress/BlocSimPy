import os
import json
import uuid
from state import deployments, server_lock, CONFIG_FILE, API_KEY
from deployment import deploy_graph_internal
import state as state_module # To modify global API_KEY via module reference if needed? No, dicts are mutable but API_KEY is string.

def save_state():
    """Saves the current deployments and API key to a JSON file."""
    deployment_list = []
    with server_lock:
        for dep_id, info in deployments.items():
            if "source_data" in info:
                deployment_list.append({
                    "id": dep_id,
                    "data": info["source_data"],
                    "status": info["status"]
                })
    
    state_data = {
        "api_key": state_module.API_KEY, # use the module level var
        "deployments": deployment_list
    }

    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(state_data, f, indent=2)
        print(f"State saved to {CONFIG_FILE}", flush=True)
    except Exception as e:
        print(f"Error saving state: {e}", flush=True)

def load_state():
    """Loads deployments and API key from the config file."""
    if not os.path.exists(CONFIG_FILE):
        state_module.API_KEY = str(uuid.uuid4())
        print(f"Initialized new API Key: {state_module.API_KEY}", flush=True)
        save_state()
        return

    print(f"Loading state from {CONFIG_FILE}...", flush=True)
    try:
        with open(CONFIG_FILE, 'r') as f:
            data = json.load(f)
        
        # Migration for old list format
        if isinstance(data, list):
            deployment_list = data
            state_module.API_KEY = str(uuid.uuid4()) # Generate new key on migration
            print(f"Migrated legacy state. New API Key: {state_module.API_KEY}", flush=True)
        else:
            deployment_list = data.get("deployments", [])
            state_module.API_KEY = data.get("api_key")
            if not state_module.API_KEY:
                state_module.API_KEY = str(uuid.uuid4())
                print(f"Generated missing API Key: {state_module.API_KEY}", flush=True)

        print(f"Server API Key: {state_module.API_KEY}", flush=True)
        
        for item in deployment_list:
            try:
                status = item.get("status", "Running")
                deploy_graph_internal(item["data"], dep_id=item["id"], initial_status=status)
                print(f"  Restored {item['id']} ({status})", flush=True)
            except Exception as e:
                print(f"  Failed to restore {item.get('id')}: {e}", flush=True)
                
    except Exception as e:
        print(f"Error loading state: {e}", flush=True)
