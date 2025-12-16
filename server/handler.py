import http.server
import json
import sys
import traceback
from state import deployments, server_lock
from persistence import save_state
from deployment import deploy_graph_internal
import state as state_module

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
        

    def is_authorized(self):
        auth_header = self.headers.get("X-API-Key")
        if not auth_header:
            auth_header = self.headers.get("Authorization")
        
        # Simple match
        return auth_header == state_module.API_KEY

    def check_auth_Or_401(self):
        if not self.is_authorized():
            self._send_json({"error": "Unauthorized"}, 401)
            return False
        return True

    def do_GET(self):
        print(f"GET request: {self.path}", flush=True)
        
        if self.path == "/deployments":
            if not self.check_auth_Or_401(): return

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
        
        elif self.path.startswith("/api/deployments/"):
            # Generic Routing: /api/deployments/{id}/{relative_path}
            if not self.check_auth_Or_401(): return
            
            # parts: ["", "api", "deployments", "dep_id", ...rest]
            parts = self.path.split("/")
            if len(parts) < 5:
                self._send_json({"error": "Invalid API path"}, 400)
                return
                
            dep_id = parts[3]
            # Reconstruct relative path
            # parts[4:] join with /
            rel_path = "/".join(parts[4:])
            
            with server_lock:
                dep = deployments.get(dep_id)
                if not dep:
                    self._send_json({"error": "Deployment not found"}, 404)
                    return
                
                # Check routes
                api_routes = dep.get("api_routes", {})
                handler = api_routes.get(rel_path)
                
                if not handler:
                    self._send_json({"error": f"Endpoint '{rel_path}' not found"}, 404)
                    return
                
                # Delegate to handler
                try:
                    if hasattr(handler, "handle_get"):
                        resp = handler.handle_get()
                        self._send_json(resp)
                    else:
                        self._send_json({"error": "Method GET not supported by this endpoint"}, 405)
                except Exception as e:
                    self._send_json({"error": f"Handler error: {str(e)}"}, 500)
                
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
            if not self.check_auth_Or_401(): return

            try:
                # Use internal helper
                dep_id = deploy_graph_internal(data)
                
                # Save state
                save_state()
                
                print(f"  -> Success: {dep_id}", flush=True)
                self._send_json({"id": dep_id, "message": "Deployed successfully"})
                
            except Exception as e:
                error_msg = traceback.format_exc()
                print(f"  -> Failed: {e}\n{error_msg}", flush=True)
                self._send_json({"error": str(e), "traceback": error_msg}, 500)

        elif self.path == "/control":
            if not self.check_auth_Or_401(): return

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
                    state_changed = False
                    if action == "stop":
                        if info["status"] == "Running":
                            stream.stop()
                            info["status"] = "Stopped"
                            state_changed = True
                            
                    elif action == "start":
                        if info["status"] == "Stopped":
                            stream.start()
                            info["status"] = "Running"
                            state_changed = True
                            
                    elif action == "delete":
                        stream.stop()
                        if hasattr(stream, 'close'): stream.close()
                        del deployments[dep_id]
                        print(f"  Deleted {dep_id}", flush=True)
                        state_changed = True
                        
                    if state_changed:
                        save_state()
                        
                    self._send_json({"message": f"Action {action} completed"})
                except Exception as e:
                    print(f"  Control Error: {e}", flush=True)
                    self._send_json({"error": str(e)}, 500)

        elif self.path.startswith("/api/deployments/"):
            # Generic Routing: /api/deployments/{id}/{relative_path}
            if not self.check_auth_Or_401(): return

            # parts: ["", "api", "deployments", "dep_id", ...rest]
            parts = self.path.split("/")
            if len(parts) < 5:
                self._send_json({"error": "Invalid API path"}, 400)
                return
                
            dep_id = parts[3]
            rel_path = "/".join(parts[4:])
            
            with server_lock:
                dep = deployments.get(dep_id)
                if not dep:
                    self._send_json({"error": "Deployment not found"}, 404)
                    return
                
                # Check routes
                api_routes = dep.get("api_routes", {})
                handler = api_routes.get(rel_path)
                
                if not handler:
                    self._send_json({"error": f"Endpoint '{rel_path}' not found"}, 404)
                    return

                # Delegate to handler
                try:
                    if hasattr(handler, "handle_post"):
                        resp = handler.handle_post(data)
                        self._send_json(resp)
                    else:
                        self._send_json({"error": "Method POST not supported by this endpoint"}, 405)
                except Exception as e:
                    self._send_json({"error": f"Handler error: {str(e)}"}, 500)

        else:
            self.send_response(404)
            self.end_headers()
