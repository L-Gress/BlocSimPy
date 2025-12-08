"""Manages dock widgets (library, etc)."""
from PySide6.QtWidgets import QDockWidget, QListWidget, QWidget, QVBoxLayout, QLineEdit, QLabel
from PySide6.QtCore import Qt
from engine.blocks import BLOCK_REGISTRY
from ..library import UserLibraryWidget


class DockManager:
    """Manages dock widgets in the main window."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.library_dock = None
        self.user_library_widget = None
        
    def create_library_dock(self):
        """Create the library dock with block list and user library."""
        from PySide6.QtWidgets import QTabWidget
        
        # Create dock
        self.library_dock = QDockWidget("Library", self.main_window)
        self.library_dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)
        
        # Container widget with tabs
        library_container = QWidget()
        library_layout = QVBoxLayout(library_container)
        library_layout.setContentsMargins(0, 0, 0, 0)
        
        # Tab widget
        library_tabs = QTabWidget()
        
        # Tab 1: Block Library
        blocks_tab = QWidget()
        blocks_layout = QVBoxLayout(blocks_tab)
        blocks_layout.setContentsMargins(5, 5, 5, 5)
        
        # Search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText("Search blocks...")
        search_bar.textChanged.connect(self._filter_blocks)
        blocks_layout.addWidget(search_bar)
        
        # Block list
        self.block_list = QListWidget()
        self.block_list.itemDoubleClicked.connect(self.main_window.scene_manager.add_block_to_scene)
        blocks_layout.addWidget(self.block_list)
        
        # Populate block list
        for block_name in sorted(BLOCK_REGISTRY.keys()):
            self.block_list.addItem(block_name)
        
        library_tabs.addTab(blocks_tab, "Blocks")
        
        # Tab 2: User Library
        self.user_library_widget = UserLibraryWidget()
        self.user_library_widget.load_requested.connect(
            self.main_window.scene_manager.spawn_subgraph_from_library
        )
        library_tabs.addTab(self.user_library_widget, "User Library")
        
        library_layout.addWidget(library_tabs)
        
        self.library_dock.setWidget(library_container)
        return self.library_dock
    
    def toggle_library(self):
        """Toggle visibility of the library dock."""
        if self.library_dock:
            self.library_dock.setVisible(not self.library_dock.isVisible())
    
    def _filter_blocks(self, search_text):
        """Filter blocks in the library list based on search text."""
        search_lower = search_text.lower()
        for i in range(self.block_list.count()):
            item = self.block_list.item(i)
            item.setHidden(search_lower not in item.text().lower())
