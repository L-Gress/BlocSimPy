import http.server
import sys
import threading
import http.server
import json
import sys
import os
import threading

# Add parent directory to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from persistence import load_state
from handler import RequestHandler
from state import deployments

def run_server(port=8080):
    server_address = ('', port)
    # Using ThreadingHTTPServer if available for better concurrent handling,
    # or just HTTPServer. HTTPServer is single threaded by default.
    # To properly handle blocking requests (if any), ThreadingHTTPServer is better,
    # but base http.server might be enough for this simple usage.
    # However, to support clean Ctrl+C, we can use a small loop or 
    # just handle the interrupt cleanly.
    
    httpd = http.server.HTTPServer(server_address, RequestHandler)
    print(f"Realtime Server (Multi-Session) listening on port {port}...", flush=True)
    
    load_state()
    print("Buffer log initialized.", flush=True)
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down server...", flush=True)
    finally:
        httpd.server_close()
        # Clean up deployments
        for dep in deployments.values():
            try:
                if "stream" in dep:
                    dep["stream"].stop()
                    if hasattr(dep["stream"], 'close'):
                        dep["stream"].close()
            except: pass
        print("Server stopped.", flush=True)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    else:
        port = 8080
    run_server(port)
