import threading
import os

deployments = {}
server_lock = threading.RLock()
CONFIG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "server_state.json")
API_KEY = None
