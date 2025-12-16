import tkinter as tk
from tkinter import ttk, messagebox
import requests
import json
import os

SERVER_URL = "http://localhost:8080"
ENDPOINT_ID = "audioVolume"

def load_api_key():
    try:
        # Assuming script is run from project root or examples folder
        # Try relative to this script file
        base_dir = os.path.dirname(os.path.abspath(__file__))
        config_path = os.path.join(base_dir, "..", "server", "server_state.json")
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                data = json.load(f)
                return data.get("api_key")
    except Exception as e:
        print(f"Failed to load API key: {e}")
    return None

class VolumeControlGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Volume Controller")
        self.root.geometry("400x350")
        
        self.api_key = load_api_key()
        
        # API Key Display (Optional, for verification)
        tk.Label(root, text="API Key:").pack(pady=(5,0))
        self.api_key_entry = tk.Entry(root)
        self.api_key_entry.pack(fill=tk.X, padx=20)
        if self.api_key:
            self.api_key_entry.insert(0, self.api_key)
        
        # Deployment Selection
        tk.Label(root, text="Select Deployment:").pack(pady=5)
        self.deployment_combo = ttk.Combobox(root, state="readonly")
        self.deployment_combo.pack(fill=tk.X, padx=20)
        self.deployment_combo.bind("<<ComboboxSelected>>", self.on_deployment_select)
        
        # Refresh Button
        tk.Button(root, text="Refresh List", command=self.refresh_deployments).pack(pady=5)
        
        # Volume Control
        self.control_frame = tk.Frame(root)
        self.control_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        tk.Label(self.control_frame, text="Volume Control", font=("Arial", 12, "bold")).pack(pady=10)
        
        self.volume_var = tk.DoubleVar(value=0.0)
        self.slider = ttk.Scale(
            self.control_frame, 
            from_=0.0, 
            to=2.0, 
            orient=tk.HORIZONTAL, 
            variable=self.volume_var,
            command=self.on_slider_change
        )
        self.slider.pack(fill=tk.X)
        
        self.value_label = tk.Label(self.control_frame, text="0.00")
        self.value_label.pack(pady=5)
        
        # Status Label
        self.status_label = tk.Label(root, text="Ready", bd=1, relief=tk.SUNKEN, anchor=tk.W)
        self.status_label.pack(side=tk.BOTTOM, fill=tk.X)
        
        self.control_frame.pack_forget() # Hide until selection
        
        self.refresh_deployments()

    @property
    def headers(self):
        key = self.api_key_entry.get().strip()
        return {"X-API-Key": key} if key else {}

    def refresh_deployments(self):
        try:
            resp = requests.get(f"{SERVER_URL}/deployments", headers=self.headers)
            resp.raise_for_status()
            deployments = resp.json()
            
            values = []
            self.deployment_ids = {}
            for d in deployments:
                name = d.get("name", "Untitled")
                dep_id = d.get("id")
                status = d.get("status")
                label = f"{name} ({status}) [{dep_id}]"
                values.append(label)
                self.deployment_ids[label] = dep_id
                
            self.deployment_combo['values'] = values
            if values:
                self.deployment_combo.current(0)
                self.on_deployment_select(None)
            else:
                self.deployment_combo.set("No deployments found")
                self.control_frame.pack_forget()
                
        except Exception as e:
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")

    def on_deployment_select(self, event):
        label = self.deployment_combo.get()
        if label in self.deployment_ids:
            self.control_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
            self.current_id = self.deployment_ids[label]
            self.status_label.config(text=f"Connected to {self.current_id}")

    def on_slider_change(self, val):
        val_float = float(val)
        self.value_label.config(text=f"{val_float:.2f}")
        
        # Debounce or send immediately? Sending immediately might flood default python http server.
        # But for localhost it's usually fine.
        self.send_update(val_float)

    def send_update(self, value):
        if not hasattr(self, 'current_id'): return
        
        url = f"{SERVER_URL}/api/deployments/{self.current_id}/inputs/{ENDPOINT_ID}"
        try:
            payload = {"value": value}
            requests.post(url, json=payload, headers=self.headers, timeout=0.5)
            self.status_label.config(text=f"Sent: {value:.2f}")
        except Exception as e:
            self.status_label.config(text=f"Error: {str(e)}")
            print(f"Error sending update: {e}")

if __name__ == "__main__":
    root = tk.Tk()
    app = VolumeControlGUI(root)
    root.mainloop()
