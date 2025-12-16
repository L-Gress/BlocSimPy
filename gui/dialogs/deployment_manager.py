from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget, 
                               QTableWidgetItem, QPushButton, QHeaderView, QMessageBox, QLabel, QLineEdit)
import urllib.request
import json
from .deploy_dialog import DeployDialog

class DeploymentManagerDialog(QDialog):
    """Dialog to view and manage active deployments on the Realtime Server."""
    
    def __init__(self, parent=None, server_url="http://localhost:8080"):
        super().__init__(parent)
        self.setWindowTitle("Deployment Manager")
        self.resize(600, 400)
        self.server_url = server_url
        
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel(f"Server: {server_url}"))
        
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setPlaceholderText("API Key")
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setFixedWidth(150)
        header_layout.addWidget(self.api_key_edit)
        
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.clicked.connect(self.refresh_list)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)
        
        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["ID", "Name", "Status", "Config"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        layout.addWidget(self.table)
        
        # Actions
        btn_layout = QHBoxLayout()
        
        btn_start = QPushButton("▶ Start")
        btn_start.setStyleSheet("color: green;")
        btn_start.clicked.connect(lambda: self.control_action("start"))
        
        btn_stop = QPushButton("⏹ Stop")
        btn_stop.setStyleSheet("color: orange;")
        btn_stop.clicked.connect(lambda: self.control_action("stop"))
        
        btn_delete = QPushButton("❌ Delete")
        btn_delete.setStyleSheet("color: red;")
        btn_delete.clicked.connect(lambda: self.control_action("delete"))
        
        btn_close = QPushButton("Close")
        btn_close.clicked.connect(self.accept)
        
        btn_layout.addWidget(btn_start)
        btn_layout.addWidget(btn_stop)
        btn_layout.addWidget(btn_delete)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        
        # Initial Load
        self.refresh_list()
        
    def refresh_list(self):
        """Fetch deployments from server."""
        self.table.setRowCount(0)
        try:
            url = self.server_url + "/deployments"
            req = urllib.request.Request(url)
            key = self.api_key_edit.text()
            if key: req.add_header('X-API-Key', key)
            
            with urllib.request.urlopen(req) as f:
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
            # simple error log in table
            self.table.setRowCount(0)
            # QMessageBox.warning(self, "Connection Error", f"Could not reach server: {e}")

    def control_action(self, action):
        """Send control command."""
        selected_items = self.table.selectedItems()
        if not selected_items:
            return
            
        row = selected_items[0].row()
        dep_id = self.table.item(row, 0).text()
        
        try:
            url = self.server_url + "/control"
            payload = {"action": action, "id": dep_id}
            data = json.dumps(payload).encode('utf-8')
            
            req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
            key = self.api_key_edit.text()
            if key: req.add_header('X-API-Key', key)
            with urllib.request.urlopen(req) as f:
                # resp = json.loads(f.read().decode('utf-8'))
                pass
                
            self.refresh_list()
            
        except Exception as e:
            QMessageBox.warning(self, "Action Failed", f"Command failed: {e}")
