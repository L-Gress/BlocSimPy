"""Main window orchestrator - delegates to managers."""
from PySide6.QtWidgets import QMainWindow, QLabel, QWidget, QVBoxLayout
from PySide6.QtCore import Qt
from config.ui_config import UIConfig
from .scene import NodeScene
from .widgets import GraphicsView
from .managers import ToolbarManager, SceneManager, DockManager, ScriptManager
from .dialogs import HelpDialog


class MainWindow(QMainWindow):
    """
    Main application window - orchestrates managers.
    
    This class is now a lightweight orchestrator that delegates
    all major responsibilities to specialized manager classes.
    """
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle(UIConfig.WINDOW_TITLE)
        self.resize(UIConfig.WINDOW_WIDTH, UIConfig.WINDOW_HEIGHT)
        
        # --- Initialize Managers ---
        self.scene_manager = SceneManager(self)
        self.toolbar_manager = ToolbarManager(self)
        self.dock_manager = DockManager(self)
        self.script_manager = ScriptManager(self)
        
        # --- Scene Setup ---
        self.scene = NodeScene(self)
        
        # --- View Setup ---
        self.view = GraphicsView()
        self.view.setScene(self.scene)
        self.setCentralWidget(self.view)
        
        # --- Toolbar Setup ---
        toolbar = self.toolbar_manager.create_toolbar()
        self.addToolBar(toolbar)
        
        # --- Status Bar with Breadcrumb ---
        breadcrumb = QLabel("📍 Location: Top Level")
        self.statusBar().addWidget(breadcrumb)
        self.scene_manager.breadcrumb_label = breadcrumb
        
        # --- Library Dock ---
        library_dock = self.dock_manager.create_library_dock()
        self.addDockWidget(Qt.LeftDockWidgetArea, library_dock)
        
        # Store reference to user library widget for access by scene_manager
        self.user_library_widget = self.dock_manager.user_library_widget
    
    def show_help(self):
        """Show help dialog."""
        dialog = HelpDialog(self)
        dialog.exec()
    
    def enter_subsystem(self, subsystem_ui_block):
        """Delegate to scene_manager to enter a subsystem."""
        self.scene_manager.enter_subsystem(subsystem_ui_block)
