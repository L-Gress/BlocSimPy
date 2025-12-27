"""
Unified Cloud Manager for deploying and managing projects on the Realtime Server.
Combines deployment settings with active deployment management.
"""
import json
import urllib.request
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
    QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, 
    QLabel, QLineEdit, QGroupBox, QFrame, QFileDialog
)
from PySide6.QtCore import Qt
from engine.serialization import GraphSerializer

class CloudManagerDialog(QDialog):
    """
    Ergonomic dashboard for Realtime Server interactions.
    """
    
    def __init__(self, parent=None, default_url="http://localhost:8080"):
        super().__init__(parent)
        self.setWindowTitle("☁️ Cloud Manager")
        self.resize(750, 550)
        self.server_url = default_url
        self.main_window = parent
        
        self._setup_ui()
        self.refresh_list()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        
        # --- 1. Server Configuration ---
        server_group = QGroupBox("🔗 Server Configuration")
        server_layout = QHBoxLayout(server_group)
        
        self.url_edit = QLineEdit(self.server_url)
        self.url_edit.setPlaceholderText("http://localhost:8080")
        server_layout.addWidget(QLabel("URL:"))
        server_layout.addWidget(self.url_edit)
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("API Key (Optional)")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setFixedWidth(150)
        server_layout.addWidget(QLabel("Key:"))
        server_layout.addWidget(self.api_key_edit)
        
        btn_refresh = QPushButton("🔄 Refresh Status")
        btn_refresh.clicked.connect(self.refresh_list)
        btn_refresh.setStyleSheet("font-weight: bold; padding: 5px 15px;")
        server_layout.addWidget(btn_refresh)
        
        layout.addWidget(server_group)
        
        # --- 2. Deployment Actions ---
        deploy_group = QGroupBox("🚀 Project Deployment")
        deploy_layout = QHBoxLayout(deploy_group)
        
        btn_deploy_current = QPushButton("🚀 Deploy Current Scene")
        btn_deploy_current.setStyleSheet("background-color: #2E86AB; color: white; font-weight: bold; padding: 10px;")
        btn_deploy_current.clicked.connect(self.deploy_current_scene)
        deploy_layout.addWidget(btn_deploy_current)
        
        btn_deploy_json = QPushButton("📂 Deploy from JSON File")
        btn_deploy_json.clicked.connect(self.deploy_from_file)
        btn_deploy_json.setStyleSheet("padding: 10px;")
        deploy_layout.addWidget(btn_deploy_json)
        
        layout.addWidget(deploy_group)
        
        # --- 3. Active Deployments (Management) ---
        manage_group = QGroupBox("📡 Active Deployments")
        manage_layout = QVBoxLayout(manage_group)
        
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Status", "Config"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        manage_layout.addWidget(self.table)
        
        # Inline Controls for Management
        controls_layout = QHBoxLayout()
        
        btn_start = QPushButton("▶ Start")
        btn_start.setStyleSheet("color: #4CAF50; font-weight: bold;")
        btn_start.clicked.connect(lambda: self.control_action("start"))
        
        btn_stop = QPushButton("⏹ Stop")
        btn_stop.setStyleSheet("color: #FF9800; font-weight: bold;")
        btn_stop.clicked.connect(lambda: self.control_action("stop"))
        
        btn_delete = QPushButton("🗑 Delete")
        btn_delete.setStyleSheet("color: #F44336; font-weight: bold;")
        btn_delete.clicked.connect(lambda: self.control_action("delete"))
        
        controls_layout.addWidget(btn_start)
        controls_layout.addWidget(btn_stop)
        controls_layout.addWidget(btn_delete)
        controls_layout.addStretch()
        
        manage_layout.addLayout(controls_layout)
        layout.addWidget(manage_group)
        
        # Footer
        footer = QHBoxLayout()
        footer.addStretch()
        btn_close = QPushButton("Done")
        btn_close.setFixedWidth(100)
        btn_close.clicked.connect(self.accept)
        footer.addWidget(btn_close)
        layout.addLayout(footer)

    def _get_server_url(self):
        return self.url_edit.text().strip("/")

    def refresh_list(self):
        """Fetch deployments from server."""
        self.table.setRowCount(0)
        server_url = self._get_server_url()
        try:
            url = f"{server_url}/deployments"
            req = urllib.request.Request(url)
            key = self.api_key_edit.text()
            if key: req.add_header('X-API-Key', key)
            
            with urllib.request.urlopen(req, timeout=3) as f:
                data = json.loads(f.read().decode('utf-8'))
                
            for dep in data:
                row = self.table.rowCount()
                self.table.insertRow(row)
                self.table.setItem(row, 0, QTableWidgetItem(dep.get("id")))
                self.table.setItem(row, 1, QTableWidgetItem(dep.get("name")))
                self.table.setItem(row, 2, QTableWidgetItem(dep.get("status")))
                
                config = dep.get('config', {})
                config_str = f"{config.get('execution_mode', 'Audio')} | Rate: {config.get('sample_rate')}"
                self.table.setItem(row, 3, QTableWidgetItem(config_str))
                
        except Exception as e:
            # Table remains empty on failure
            pass

    def deploy_current_scene(self):
        """Deploy the current graph from the main window."""
        if not self.main_window or not self.main_window.scene_manager.blocks_ui:
            QMessageBox.warning(self, "Empty Scene", "There is nothing to deploy.")
            return

        # Check for InputPorts
        for ui_block in self.main_window.scene_manager.blocks_ui:
            if ui_block.model.__class__.__name__ == "InputPort":
                QMessageBox.warning(self, "Deploy Error", "Cannot deploy a SubGraph with Input Ports.")
                return

        # Prepare payload
        settings = {
            "execution_mode": "Auto Detect", 
            "sample_rate": 44100,
            "buffer_size": 1024
        }
        
        # Sync settings if in subsystem
        if self.main_window.scene_manager.subsystem_stack:
            context = self.main_window.scene_manager.subsystem_stack[-1]
            container = context.get("subsystem_model")
            if container:
                settings["execution_mode"] = container.params.get("Execution Mode", "Standard")
                try: settings["sample_rate"] = float(container.params.get("Sample Rate", 44100.0))
                except: pass

        graph_data = GraphSerializer.serialize_graph(self.main_window.scene_manager.blocks_ui)
        payload = {"graph": graph_data, "config": settings}
        
        self._send_deployment(payload)

    def deploy_from_file(self):
        """Deploy from a JSON file."""
        filename, _ = QFileDialog.getOpenFileName(self, "Open Deployment JSON", "", "JSON Files (*.json)")
        if not filename: return
            
        try:
            with open(filename, 'r') as f:
                payload = json.load(f)
            self._send_deployment(payload)
        except Exception as e:
            QMessageBox.critical(self, "File Error", f"Failed to read JSON: {e}")

    def _send_deployment(self, payload):
        """Internal helper to send deployment request."""
        try:
            url = f"{self._get_server_url()}/deploy"
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            key = self.api_key_edit.text()
            if key: req.add_header('X-API-Key', key)
            
            with urllib.request.urlopen(req) as f:
                resp = f.read().decode('utf-8')
                QMessageBox.information(self, "Deploy Success", f"Server Response: {resp}")
                self.refresh_list()
        except Exception as e:
            QMessageBox.critical(self, "Deploy Failed", f"Could not reach server: {e}")

    def control_action(self, action):
        """Send control command to a selected deployment."""
        selected_items = self.table.selectedItems()
        if not selected_items: return
            
        row = selected_items[0].row()
        dep_id = self.table.item(row, 0).text()
        
        try:
            url = f"{self._get_server_url()}/control"
            payload = {"action": action, "id": dep_id}
            data = json.dumps(payload).encode('utf-8')
            
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            key = self.api_key_edit.text()
            if key: req.add_header('X-API-Key', key)
            with urllib.request.urlopen(req) as f:
                f.read() # Consume response
                
            self.refresh_list()
        except Exception as e:
            QMessageBox.warning(self, "Action Failed", f"Command failed: {e}")
