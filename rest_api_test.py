import urllib.request
import json
import time
import os
import sys

# Configuration
SERVER_URL = "http://localhost:8080"
SERVER_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server")
STATE_FILE = os.path.join(SERVER_DIR, "server_state.json")

def get_api_key():
    """Reads the API Key from the server state file."""
    if not os.path.exists(STATE_FILE):
        print(f"Error: {STATE_FILE} not found. Is the server running?")
        sys.exit(1)
    
    try:
        with open(STATE_FILE, "r") as f:
            data = json.load(f)
            # Handle both migration generic wrapper and direct dict
            if isinstance(data, dict):
                key = data.get("api_key")
                if key: return key
                
        print("Error: Could not find 'api_key' in server state.")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading state file: {e}")
        sys.exit(1)

def send_request(method, endpoint, data=None, api_key=None):
    url = f"{SERVER_URL}{endpoint}"
    if data:
        body = json.dumps(data).encode('utf-8')
    else:
        body = None
    
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('Content-Type', 'application/json')
    if api_key:
        req.add_header('X-API-Key', api_key)
        
    try:
        with urllib.request.urlopen(req) as f:
            resp_body = f.read().decode('utf-8')
            return json.loads(resp_body) if resp_body else {}
    except urllib.error.HTTPError as e:
        print(f"Request failed: {e.code} {e.reason}")
        print(e.read().decode('utf-8'))
        sys.exit(1)
    except Exception as e:
        print(f"Request error: {e}")
        sys.exit(1)

def main():
    print("--- REST API Test ---")
    
    # 1. Get API Key
    api_key = get_api_key()
    print(f"API Key: {api_key}")
    
    # 2. Define Graph (Input -> Gain(x2) -> Output)
    graph_payload = {
        "name": "API Test Graph",
        "config": {
            "execution_mode": "Timer Driven",
            "sample_rate": 100,
            "buffer_size": 1
        },
        "graph": {
            "blocks": [
                {
                    "id": "src",
                    "type": "RestInput",
                    "params": {"Endpoint ID": "test_in", "Data Type": "float", "Initial Value": "1.0"}
                },
                {
                    "id": "gain",
                    "type": "Gain",
                    "params": {"Gain": "2.0"}
                },
                {
                    "id": "snk",
                    "type": "RestOutput",
                    "params": {"Endpoint ID": "test_out", "Data Type": "float"}
                }
            ],
            "connections": [
                {
                    "from_block_id": "src", "from_port": "out",
                    "to_block_id": "gain", "to_port": "in"
                },
                {
                    "from_block_id": "gain", "from_port": "out",
                    "to_block_id": "snk", "to_port": "in"
                }
            ]
        }
    }
    
    # 3. Deploy
    print("\nDeploying graph...")
    resp = send_request("POST", "/deploy", graph_payload, api_key)
    dep_id = resp.get("id")
    print(f"Deployed ID: {dep_id}")
    
    # Wait a moment for server to initialize
    time.sleep(0.5)
    
    # 4. Test Loop
    test_values = [10.0, 25.5, -5.0, 0.0]
    
    for val in test_values:
        print(f"\nTesting Input: {val}")
        
        # Set Input
        endpoint_in = f"/api/deployments/{dep_id}/inputs/test_in"
        send_request("POST", endpoint_in, {"value": val}, api_key)
        
        # Wait a tick (Timer is 100Hz, so 0.01s is enough, safe 0.1s)
        time.sleep(0.1)
        
        # Get Output
        endpoint_out = f"/api/deployments/{dep_id}/outputs/test_out"
        res = send_request("GET", endpoint_out, None, api_key)
        
        out_val = res.get("value")
        expected = val * 2.0
        
        print(f"  Output: {out_val}")
        
        if abs(out_val - expected) < 0.001:
            print("  [PASS]")
        else:
            print(f"  [FAIL] Expected {expected}")

    # 5. Clean up (Optional - Delete deployment)
    print(f"\nCleaning up {dep_id}...")
    send_request("POST", "/control", {"action": "delete", "id": dep_id}, api_key)
    print("Done.")

if __name__ == "__main__":
    main()
