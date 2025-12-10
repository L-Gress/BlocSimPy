"""Manages dock widgets (library, etc)."""
from PySide6.QtWidgets import QDockWidget, QTreeWidget, QTreeWidgetItem, QWidget, QVBoxLayout, QLineEdit, QLabel, QTabWidget
from PySide6.QtCore import Qt
from engine.blocks import BLOCK_REGISTRY
from ..library import UserLibraryWidget


class DockManager:
    """Manages dock widgets in the main window."""
    
    def __init__(self, main_window):
        self.main_window = main_window
        self.library_dock = None
        self.user_library_widget = None
        self.block_tree = None
        
    def create_library_dock(self):
        """Create the library dock with categorized block tree and user library."""
        
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
        
        # Block Tree
        self.block_tree = QTreeWidget()
        self.block_tree.setHeaderHidden(True)
        self.block_tree.itemDoubleClicked.connect(self._on_tree_double_click)
        blocks_layout.addWidget(self.block_tree)
        
        # Populate block tree
        self._populate_library()
        
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
    
    def _populate_library(self):
        """Populate the block tree with categories."""
        categories = {
            "Deployable I/O": ["AudioInput", "AudioOutput"],
            "Structure": ["SubGraph", "InputPort", "OutputPort"],
            "Standard Blocks": [] # Everything else
        }
        
        # Fill Standard Blocks
        defined_specials = set(categories["Deployable I/O"] + categories["Structure"])
        
        for name in sorted(BLOCK_REGISTRY.keys()):
            if name not in defined_specials:
                categories["Standard Blocks"].append(name)
        
        # Create Tree Items
        self.block_tree.clear()
        
        # Helper to add category
        def add_category(cat_name, block_names):
            if not block_names: return
            cat_item = QTreeWidgetItem(self.block_tree)
            cat_item.setText(0, cat_name)
            cat_item.setExpanded(True)
            
            for b_name in sorted(block_names):
                b_item = QTreeWidgetItem(cat_item)
                b_item.setText(0, b_name)
                
        # Add special categories first
        add_category("Deployable I/O", categories["Deployable I/O"])
        add_category("Structure", categories["Structure"])
        add_category("Standard Blocks", categories["Standard Blocks"])
        
    def _on_tree_double_click(self, item, column):
        """Handle tree double click - if leaf node, add block."""
        if item.childCount() == 0:
            # It's a block
            block_class_name = item.text(0)
            if block_class_name in BLOCK_REGISTRY:
                # Mock a list interface because scene_manager expects an item with .text()
                # Actually scene_manager expects an item.
                # let's modify the way we call it.
                # We can reuse the item directly because item.text(0) works, 
                # but scene_manager.add_block_to_scene calls list_item.text().
                # QTreeWidgetItem.text(column) takes an arg. list_item.text() takes 0.
                
                # We should update SceneManager to accept a string name, 
                # OR wrap this call.
                # Easiest: SceneManager.add_block_by_name
                self.main_window.scene_manager.add_block_by_name(block_class_name)

    def toggle_library(self):
        """Toggle visibility of the library dock."""
        if self.library_dock:
            self.library_dock.setVisible(not self.library_dock.isVisible())
    
    def _filter_blocks(self, search_text):
        """Filter blocks in the library tree based on search text."""
        search_lower = search_text.lower()
        root = self.block_tree.invisibleRootItem()
        
        for i in range(root.childCount()):
            category = root.child(i)
            cat_visible_children = 0
            
            for j in range(category.childCount()):
                child = category.child(j)
                text = child.text(0)
                
                if search_lower in text.lower():
                    child.setHidden(False)
                    cat_visible_children += 1
                else:
                    child.setHidden(True)
            
            # Hide category if no children visible
            category.setHidden(cat_visible_children == 0)
